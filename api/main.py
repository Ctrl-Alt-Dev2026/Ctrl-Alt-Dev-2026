"""Local API with persisted human review and read-only synthetic snapshots."""

from contextlib import asynccontextmanager
import os
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from ai.router import register_ai
from ai.patterns.router import register_patterns
from api.review_router import register_review
from api.publication_router import register_publication
from api.safecross_router import register_safecross
from api.vision_router import register_vision
from api.frontend import register_frontend
from api.live_router import register_live, start_live
from safecross.setup import MODEL_PATH
from api.snapshots import SnapshotError, load_snapshot


DEFAULT_SNAPSHOT_DIRECTORY = Path(__file__).resolve().parents[1] / "false_data"
DEFAULT_REVIEW_DIRECTORY = Path(__file__).resolve().parents[1] / "runtime" / "review"


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["safeiasi-api"] = "safeiasi-api"


class SnapshotMetadata(BaseModel):
    snapshot_id: str
    data_mode: Literal["synthetic"]
    warning: str
    eligible_event_count: int


class ManifestResponse(SnapshotMetadata):
    manifest: dict[str, Any]


class EventsResponse(SnapshotMetadata):
    events: list[dict[str, Any]]


def create_app(snapshot_directory: str | Path | None = None, review_directory: str | Path | None = None, safecross_directory: str | Path | None = None, safecross_model_path: str | Path | None = None, publication_directory: str | Path | None = None, publication_context_directory: str | Path | None = None, frontend_directory: str | Path | None = None):
    directory = Path(
        snapshot_directory if snapshot_directory is not None
        else os.environ.get("SAFEIASI_SNAPSHOT_DIR", DEFAULT_SNAPSHOT_DIRECTORY)
    ).resolve()

    @asynccontextmanager
    async def lifespan(application):
        application.state.snapshot = None
        application.state.snapshot_error = None
        try:
            application.state.snapshot = load_snapshot(directory)
        except SnapshotError as error:
            application.state.snapshot_error = error
        # Collected ISU/press data, refreshed every 30 minutes when SAFEIASI_LIVE=1 (api/live_router.py).
        scheduler = start_live(application)
        yield
        if scheduler is not None:
            scheduler.stop()

    application = FastAPI(
        title="SafeIași API", version="0.7.0", lifespan=lifespan,
        description=(
            "API local cu citire de snapshot sintetic validat. /health confirmă doar serverul. "
            "Datele lipsă/invalide produc HTTP 503 pe rutele de date. "
            "Extracția AI produce candidați neverificați; /imports îi salvează pentru review local. "
            "Corectarea și deciziile operatorului sunt versionate, fără publicare automată pe hartă. "
            "Extracția live a textului necesită Ollama; reluările salvate sunt etichetate explicit. "
            "SafeCross opțional analizează local video CFR cu YOLOX și review uman, separat de accidente. "
            "/patterns explorează ipoteze pe fixture-uri sintetice cu vectori semantici pregătiți, "
            "fără modificarea snapshot-ului sau a datelor de review. "
            "Publicarea locală este explicită, cu versiuni înghețate, context verificat și dosare exportabile. "
            "Geocodarea offline propune localizări înainte de aprobare, cu dovezi OSM și confirmarea operatorului."
        ),
    )
    application.state.review_directory = Path(
        review_directory if review_directory is not None
        else os.environ.get("SAFEIASI_REVIEW_DIR", DEFAULT_REVIEW_DIRECTORY)
    ).resolve()
    application.state.safecross_directory = Path(
        safecross_directory if safecross_directory is not None
        else os.environ.get("SAFEIASI_SAFECROSS_DIR", DEFAULT_REVIEW_DIRECTORY.parent / "safecross")
    ).resolve()
    application.state.safecross_model_path = Path(
        safecross_model_path if safecross_model_path is not None
        else os.environ.get("SAFEIASI_SAFECROSS_MODEL", MODEL_PATH)
    ).resolve()
    application.state.publication_directory = Path(
        publication_directory if publication_directory is not None
        else os.environ.get("SAFEIASI_PUBLICATION_DIR", DEFAULT_REVIEW_DIRECTORY.parent / "publications")
    ).resolve()
    application.state.publication_context_directory = Path(
        publication_context_directory if publication_context_directory is not None
        else os.environ.get("SAFEIASI_PUBLICATION_CONTEXT_DIR", DEFAULT_REVIEW_DIRECTORY.parents[1] / "context" / "output" / "observed" / "iasi")
    ).resolve()

    def snapshot_or_error(request):
        error = getattr(request.app.state, "snapshot_error", None)
        if error is not None:
            raise HTTPException(status_code=503, detail=error.detail())
        snapshot = getattr(request.app.state, "snapshot", None)
        if snapshot is None:
            raise HTTPException(status_code=503, detail={
                "code": "snapshot_unavailable", "message": "Snapshot-ul nu este încărcat.", "issues": [],
            })
        return snapshot

    @application.get("/", include_in_schema=False)
    async def index():
        return RedirectResponse(url="/docs")

    @application.get(
        "/health", response_model=HealthResponse, tags=["system"],
        summary="Verifică pornirea serverului local",
        description="Verificare a procesului, independentă de validitatea datelor și cheile API.",
    )
    async def health() -> HealthResponse:
        return HealthResponse()

    @application.get(
        "/api/v1/manifest", response_model=ManifestResponse, tags=["dataset"],
        summary="Manifestul snapshot-ului sintetic validat",
        responses={503: {"description": "Snapshot lipsă, invalid sau mod nesuportat."}},
    )
    async def manifest(request: Request):
        return snapshot_or_error(request).manifest_payload()

    @application.get(
        "/api/v1/events", response_model=EventsResponse, tags=["dataset"],
        summary="Evenimente sintetice eligibile din același snapshot",
        description=(
            "Numai înregistrări marcate verificate, în municipiu și în perioada declarată, "
            "cu localizare precisă și fără duplicate_of. Nu este clasament sau set de date reale."
        ),
        responses={503: {"description": "Snapshot lipsă, invalid sau mod nesuportat."}},
    )
    async def events(request: Request):
        return snapshot_or_error(request).events_payload()

    register_frontend(application, frontend_directory)
    register_vision(application)
    return register_live(register_publication(register_patterns(register_safecross(register_review(register_ai(application))))))


app = create_app()
