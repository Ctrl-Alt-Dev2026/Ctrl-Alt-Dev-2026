"""Backend adapter for the existing Romanian schema 2.0 article/candidate fields."""
from __future__ import annotations

import copy
import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .engine import VERSION, Ollama, digest, run

AI_DIR = Path(__file__).resolve().parent
PIPELINES = ("rules", "direct", "evidence", "agreement", "hybrid")
ARTICLE_FIELDS = {"article_id", "sursa", "url", "titlu", "text", "publicat_la", "colectat_la"}


def validate_article(article: dict) -> dict:
    if not isinstance(article, dict) or set(article) != ARTICLE_FIELDS:
        raise ValueError("article must contain exactly the seven existing v2 article fields")
    if any(not isinstance(article[key], str) for key in ARTICLE_FIELDS):
        raise ValueError("v2 article fields must be strings")
    if not article["article_id"].strip() or not article["text"].strip():
        raise ValueError("article_id and text cannot be empty")
    return copy.deepcopy(article)


@dataclass(frozen=True)
class ExtractionConfig:
    model: str = "qwen2.5:1.5b"
    base_url: str = "http://127.0.0.1:11434"
    cache_dir: Path = AI_DIR / "work" / "cache"
    timeout_s: float = 120
    retries: int = 1

    def __post_init__(self):
        parsed = urlparse(self.base_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("Ollama base_url must be an HTTP(S) endpoint")
        if self.timeout_s <= 0 or not 0 <= self.retries <= 3:
            raise ValueError("timeout must be positive; retries must be between 0 and 3")

    @classmethod
    def from_env(cls):
        return cls(
            model=os.getenv("SAFEIASI_AI_MODEL", cls.model),
            base_url=os.getenv("SAFEIASI_AI_OLLAMA_URL", cls.base_url),
            cache_dir=Path(os.getenv("SAFEIASI_AI_CACHE_DIR", str(cls.cache_dir))),
        )


class ExtractionUnavailable(RuntimeError):
    """Carries pending fallback candidates/diagnostics; never means irrelevant news."""

    def __init__(self, result: dict):
        super().__init__("AI extraction unavailable; inspect .result for pending candidates and errors")
        self.result = result


class ExtractionService:
    def __init__(self, config: ExtractionConfig | None = None, *, client=None):
        self.config = config or ExtractionConfig.from_env()
        self.client = client if client is not None else Ollama(
            model=self.config.model,
            base_url=self.config.base_url,
            cache=self.config.cache_dir,
            timeout=self.config.timeout_s,
            retries=self.config.retries,
        )
        # The current backend is a single-process local application. Serialize its
        # model/cache writes; multiple Uvicorn workers need a shared lock/store.
        self._lock = threading.RLock()

    def extract(self, article: dict, pipeline: str = "hybrid") -> dict:
        article = validate_article(article)
        if pipeline not in PIPELINES:
            raise ValueError("unsupported extraction pipeline")
        with self._lock:
            components = None
            if pipeline == "agreement":
                components = {}
                for name in ("direct", "evidence"):
                    part = run([article], name, self.client)
                    components[name] = {r["article_id"]: r for r in part["rows"]}
            result = run([article], pipeline, self.client, components)

        row = result["rows"][0]
        traces = [row["trace"]]
        if components:
            traces = [components[name][article["article_id"]]["trace"] for name in ("direct", "evidence")]
        errors = [str(error) for trace in traces if trace.get("failed")
                  for error in (trace.get("errors") or ["model extraction failed"])]
        for candidate in result["accidents"]:
            candidate["extraction_runs"] = [{
                "run_id": trace.get("cache_key", digest({"text": article["text"], "pipeline": pipeline, "version": VERSION})),
                "model": trace.get("model", self.config.model if pipeline != "rules" else "rules"),
                "prompt_version": trace.get("prompt_version", VERSION),
                "content_hash": row["content_hash"],
                "published_at": row["published_at"],
                "retrieved_at": row["retrieved_at"],
            } for trace in traces]
            if errors:
                candidate["issues"].append("ai_unavailable_requires_review")
        if pipeline == "rules":
            processing_mode = "rules"
        elif errors:
            processing_mode = "rules_fallback" if result["accidents"] else "unavailable"
        else:
            processing_mode = "cache" if all(t.get("cache_hit") for t in traces) else "live"
        return {
            "schema_version": "2.0",
            "data_mode": result["data_mode"],
            "pipeline": pipeline,
            "processing_mode": processing_mode,
            "review_status": "pending",
            "candidates": result["accidents"],
            "articles": result["rows"],
            "duplicate_review_queue": result["duplicate_review_queue"],
            "errors": errors,
        }

    def replay(self, article_id: str) -> dict:
        entries = json.loads((AI_DIR / "benchmarks" / "replays.json").read_text(encoding="utf-8"))
        for entry in entries:
            if entry["article_id"] == article_id:
                if entry["data_mode"] != "synthetic" or entry["candidate"]["verificat"] is not False:
                    raise ValueError("replay artifact must remain synthetic and unapproved")
                return {
                    "schema_version": "2.0", "data_mode": "synthetic",
                    "processing_mode": "replay", "review_status": "pending",
                    "label": "SYNTHETIC REPLAY — saved extraction, not live AI",
                    "candidates": [copy.deepcopy(entry["candidate"])],
                    "articles": [copy.deepcopy(entry["row"])],
                    "duplicate_review_queue": [], "errors": [],
                }
        raise KeyError(article_id)


def extract_article(article: dict, *, pipeline: str = "hybrid", config: ExtractionConfig | None = None) -> list[dict]:
    """Backend seam: extract_article(article) -> pending v2 candidate list.

    Raises ValueError for invalid input and ExtractionUnavailable for provider
    errors. The latter carries explicitly marked rules fallback in .result.
    """
    result = ExtractionService(config).extract(article, pipeline)
    if result["errors"]:
        raise ExtractionUnavailable(result)
    return result["candidates"]
