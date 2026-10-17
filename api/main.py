"""Local API and read-only synthetic snapshot access for SafeIasi."""

from contextlib import asynccontextmanager
import os
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from api.snapshots import SnapshotError, load_snapshot


DEFAULT_SNAPSHOT_DIRECTORY = Path(__file__).resolve().parents[1] / "false_data"


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


def create_app(snapshot_directory: str | Path | None = None):
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
        yield

    application = FastAPI(
        title="SafeIași API", version="0.2.0", lifespan=lifespan,
        description=(
            "API local cu citire de snapshot sintetic validat. /health confirmă doar serverul. "
            "Datele lipsă/invalide produc HTTP 503 pe rutele de date. "
            "Extracția AI și publicarea datelor observate urmează separat."
        ),
    )

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

    return application


app = create_app()
