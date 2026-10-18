"""Prepare only validated, complete Gemini cache batches for repository sharing."""
import hashlib
import json
from pathlib import Path

from .engine import atomic_json, digest
from .gemini_client import DEFAULT_MODEL
from .gemini_pipeline import PROMPT_VERSION, SHARED_CACHE, WORK, build_prompt, parse_response
from .press_pipeline import DEFAULT_CSV, _article, _read


def export_cache(source=DEFAULT_CSV, destination=SHARED_CACHE, model=DEFAULT_MODEL):
    source, destination = Path(source), Path(destination)
    rows = _read(source)[1]
    articles = [_article(row, index) for index, row in enumerate(rows, 1)]
    batches = []
    # Preflight every batch before publishing a new manifest.
    for offset in range(0, len(articles), 4):
        batch = articles[offset:offset + 4]
        prompt = build_prompt(batch)
        key = digest({"prompt": prompt, "model": model})
        paths = [WORK / "responses" / (key + suffix) for suffix in (".json", ".raw.json")]
        path = next((path for path in paths if path.exists()), None)
        if path is None:
            raise ValueError(f"Lipsește lotul {offset // 4 + 1}; pachetul complet nu poate fi exportat.")
        response = json.loads(path.read_text(encoding="utf-8"))["response"]
        reserialized = json.dumps({"prompt": prompt, "response": response}, ensure_ascii=False)
        if "AIza" in reserialized:
            raise ValueError("Posibilă cheie API în răspuns; verificare necesară înainte de partajare.")
        parse_response(response, batch)
        batches.append((key, {"prompt": prompt, "response": response}))
    entries = []
    for key, content in batches:
        path = destination / "responses" / (key + ".json")
        atomic_json(path, content)
        entries.append({"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    manifest = {"provider": "gemini", "model": model, "prompt_version": PROMPT_VERSION,
                "source": "scraping/articole_extrase_accident_clean.csv",
                "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "article_count": len(rows), "batch_size": 4, "batch_count": len(batches),
                "review_status": "pending", "responses": entries}
    atomic_json(destination / "manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    manifest = export_cache()
    print(f"Cache pregătit: {manifest['article_count']} articole, {manifest['batch_count']} loturi.")
