"""Local live-camera inference, separate from uploaded SafeCross clip analysis."""

import threading

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from api.review_router import require_local_unless
from safecross.live import LiveVision, MAX_FRAME_BYTES, SessionConfig
from safecross.live_detector import VisionError, readiness


router = APIRouter(prefix="/api/v1/vision", tags=["live cameras"], dependencies=[Depends(require_local_unless("vision"))])
_creation_lock = threading.Lock()


def service(request):
    with _creation_lock:
        if not hasattr(request.app.state, "live_vision"):
            request.app.state.live_vision = LiveVision()
        return request.app.state.live_vision


@router.get("/status", summary="Live detector installation status; does not load or download weights")
def status():
    return readiness()


@router.post("/sessions", status_code=201, summary="Create bounded in-memory camera tracking and crosswalk configuration")
def create_session(body: SessionConfig, request: Request):
    status = readiness()
    if not status["available"]:
        raise VisionError(503, "vision_not_ready", status["message"])
    return JSONResponse(service(request).create(body), status_code=201, headers={"Cache-Control": "no-store"})


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str, request: Request):
    service(request).delete(session_id)
    return Response(status_code=204)


@router.post("/sessions/{session_id}/frames", summary="Analyse one current JPEG frame; no queue, downloads, or image persistence", openapi_extra={"requestBody": {"required": True, "content": {"image/jpeg": {"schema": {"type": "string", "format": "binary"}}}}})
async def frame(session_id: str, request: Request, sequence: int = Query(ge=0), media_time: float = Query(ge=0, allow_inf_nan=False)):
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "image/jpeg":
        raise VisionError(415, "frame_content_type", "Trimite un cadru image/jpeg.")
    chunks, total = [], 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > MAX_FRAME_BYTES:
            raise VisionError(413, "frame_too_large", "Cadrul depășește 2 MiB.")
        chunks.append(chunk)
    result = await run_in_threadpool(service(request).process, session_id, b"".join(chunks), sequence, media_time)
    return JSONResponse(result, headers={"Cache-Control": "no-store"})


async def error_handler(request, error):
    return JSONResponse(status_code=error.status, content={"detail": {"code": error.code, "message": error.message}}, headers={"Cache-Control": "no-store"})


def register_vision(application):
    if not getattr(application.state, "vision_registered", False):
        application.include_router(router)
        application.add_exception_handler(VisionError, error_handler)
        application.state.vision_registered = True
        application.openapi_schema = None
    return application
