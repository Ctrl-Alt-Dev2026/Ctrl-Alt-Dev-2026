"""Local import/review routes, independent of immutable map snapshots."""

from ipaddress import ip_address
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from ai.router import get_service
from ai.service import ExtractionService
from api.review_models import CorrectionRequest, DataMode, ImportRequest, ReviewRequest
from api.review_store import ReviewError, ReviewStore
from api.snapshots import SYNTHETIC_WARNING


def require_local(request: Request):
    """This MVP is a local operator tool, without remote accounts/authentication."""
    try:
        local_peer = request.client is not None and ip_address(request.client.host).is_loopback
    except ValueError:
        local_peer = False
    origin = request.headers.get("origin")
    expected_origin = f"{request.url.scheme}://{request.url.netloc}"
    if not local_peer or request.url.hostname not in ("localhost", "127.0.0.1", "::1") or (origin is not None and origin != expected_origin):
        raise HTTPException(status_code=403, detail="Review-ul este disponibil numai local, din aceeași origine.")


router = APIRouter(
    tags=["review"], dependencies=[Depends(require_local)],
    responses={403: {"description": "Local operator access only."}, 503: {"description": "Review storage or extraction unavailable."}},
)


def _store(request, mode):
    return ReviewStore(request.app.state.review_directory, mode)


def _metadata(mode):
    return {
        "data_mode": mode, "publication_status": "not_published", "response_origin": "stored_review",
        "warning": SYNTHETIC_WARNING if mode == "synthetic" else "Date pentru verificare locală; nu reprezintă un inventar complet al accidentelor.",
    }


@router.post(
    "/api/v1/imports", status_code=201,
    summary="Extract and save pending candidates; repeated request_id is idempotent",
    responses={200: {"description": "The identical request was already imported."}, 409: {"description": "Request/source identity conflict."}, 502: {"description": "Invalid extraction contract or evidence."}},
)
def import_article(body: ImportRequest, request: Request, service: ExtractionService = Depends(get_service)):
    store = _store(request, body.data_mode)
    existing = store.find_import(body)
    if existing is not None:
        return JSONResponse(status_code=200, content=_metadata(body.data_mode) | {"import": existing, "reused": True, "persisted": True})
    try:
        result = service.extract(body.article.model_dump(), body.pipeline)
    except ValueError as error:
        raise ReviewError(422, "invalid_article", "Articolul sau opțiunile de extracție sunt invalide.") from error
    if not isinstance(result, dict):
        raise ReviewError(502, "invalid_extraction", "Extractorul nu a returnat un rezultat structurat.")
    if result.get("errors"):
        return JSONResponse(status_code=503, content={"persisted": False, "extraction": result})
    imported, reused = store.save_import(body, result)
    return JSONResponse(status_code=200 if reused else 201, content=_metadata(body.data_mode) | {"import": imported, "reused": reused, "persisted": True})


@router.get("/api/v1/imports/{import_id}", summary="Read the saved article and historical extraction")
def get_import(import_id: str, request: Request, data_mode: DataMode = "synthetic"):
    return _metadata(data_mode) | {"import": _store(request, data_mode).get_import(import_id)}


@router.get("/api/v1/candidates", summary="List local candidates in one explicit data mode")
def list_candidates(request: Request, data_mode: DataMode = "synthetic", status: Literal["pending", "approved", "rejected", "linked"] | None = None):
    return _metadata(data_mode) | {"candidates": _store(request, data_mode).list_candidates(status)}


@router.get("/api/v1/candidates/{candidate_id}", summary="Read source text, original extraction, corrections and version")
def get_candidate(candidate_id: str, request: Request, data_mode: DataMode = "synthetic"):
    return _metadata(data_mode) | {"candidate": _store(request, data_mode).get_candidate(candidate_id)}


@router.patch("/api/v1/candidates/{candidate_id}", summary="Correct a pending candidate using its expected version", responses={409: {"description": "Stale version or finalized candidate."}, 404: {"description": "Unknown candidate in this data mode."}})
def correct_candidate(candidate_id: str, body: CorrectionRequest, request: Request):
    return _metadata(body.data_mode) | {"candidate": _store(request, body.data_mode).correct(candidate_id, body)}


@router.post("/api/v1/candidates/{candidate_id}/review", summary="Explicitly approve, reject, or link a duplicate to a canonical event", responses={409: {"description": "Stale candidate/event version or finalized candidate."}, 404: {"description": "Unknown candidate/canonical event in this data mode."}})
def review_candidate(candidate_id: str, body: ReviewRequest, request: Request):
    return _metadata(body.data_mode) | _store(request, body.data_mode).review(candidate_id, body)


@router.get("/api/v1/reviewed-events", summary="Read canonical reviewed events; does not publish them to the map")
def reviewed_events(request: Request, data_mode: DataMode = "synthetic"):
    return _metadata(data_mode) | {"events": _store(request, data_mode).list_events()}


async def review_error_handler(request, error):
    return JSONResponse(status_code=error.status, content={"detail": {"code": error.code, "message": error.message}})


def register_review(application):
    if not getattr(application.state, "safeiasi_review_routes_registered", False):
        application.include_router(router)
        application.add_exception_handler(ReviewError, review_error_handler)
        application.state.safeiasi_review_routes_registered = True
        application.openapi_schema = None
    return application
