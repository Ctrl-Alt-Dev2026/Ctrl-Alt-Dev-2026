"""Local video upload, asynchronous analysis, evidence playback and human review."""

import json
from pathlib import Path
import threading
from typing import Literal
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, ValidationError
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException

from api.review_models import DataMode, Note, Operator, Version
from api.review_router import require_local
from safecross.jobs import LIMITS, VIDEO_EXTENSIONS, VideoError, VideoJobs, readiness


WEB = Path(__file__).resolve().parents[1] / "safecross" / "web"
_MANAGER_LOCK = threading.Lock()
router = APIRouter(tags=["safecross"], dependencies=[Depends(require_local)])


class VideoReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: Version
    operator: Operator
    decision: Literal["confirmed", "dismissed"]
    note: Note


def get_jobs(request):
    with _MANAGER_LOCK:
        if not hasattr(request.app.state, "safecross_jobs"):
            request.app.state.safecross_jobs = VideoJobs(
                request.app.state.safecross_directory, request.app.state.safecross_model_path,
                getattr(request.app.state, "safecross_runner", None),
            )
        return request.app.state.safecross_jobs


@router.get("/safecross", include_in_schema=False)
def page():
    return FileResponse(WEB / "index.html", media_type="text/html", headers={"Cache-Control": "no-store"})


@router.get("/safecross/assets/{filename}", include_in_schema=False)
def asset(filename: str):
    if filename not in ("app.js", "styles.css"):
        raise HTTPException(status_code=404)
    return FileResponse(WEB / filename, media_type="text/javascript" if filename.endswith(".js") else "text/css")


@router.get("/api/v1/safecross/status", summary="Local model, video dependencies and processing limits")
def status(request: Request):
    return readiness(request.app.state.safecross_model_path)


@router.post(
    "/api/v1/safecross/jobs", status_code=202, summary="Upload a stable-view CFR clip and queue local AI analysis",
    responses={413: {"description": "Upload exceeds the local size limit."}, 429: {"description": "Local analysis queue is full."}, 503: {"description": "Install optional video dependencies/model first."}},
    openapi_extra={"requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {"type": "object", "required": ["video", "data_mode", "operator", "fixed_camera_confirmed"], "properties": {
        "video": {"type": "string", "format": "binary"}, "data_mode": {"type": "string", "enum": ["synthetic", "observed"]},
        "operator": {"type": "string"}, "fixed_camera_confirmed": {"type": "boolean"}, "roi_json": {"type": "string", "description": "Optional polygon [[x,y],...] normalized to 0..1"},
        "source_url": {"type": "string"}, "attribution": {"type": "string"}, "license": {"type": "string"},
    }}}}}},
)
async def create_job(request: Request):
    available = readiness(request.app.state.safecross_model_path)
    if not available["available"]:
        raise VideoError(503, "video_not_ready", available["message"])
    max_body = LIMITS["max_upload_bytes"] + 128 * 1024
    length = request.headers.get("content-length")
    if length:
        try:
            if int(length) > max_body:
                raise VideoError(413, "video_too_large", "Clipul depășește limita locală de 64 MiB.")
        except ValueError as error:
            raise VideoError(400, "invalid_upload", "Antet de încărcare invalid.") from error
    jobs = get_jobs(request)
    jobs.reserve()
    accepted, source_path, folder = False, None, None
    total, overflow = 0, False
    receive = request.receive

    async def bounded_receive():
        nonlocal total, overflow
        message = await receive()
        total += len(message.get("body", b""))
        if total > max_body:
            overflow = True
            raise MultiPartException("video upload limit exceeded")
        return message

    limited = Request(request.scope, receive=bounded_receive)
    try:
        async with limited.form(max_files=1, max_fields=7, max_part_size=32 * 1024) as form:
            upload = form.get("video")
            if not isinstance(upload, UploadFile):
                raise VideoError(422, "video_required", "Selectează un fișier video.")
            allowed = {"video", "data_mode", "operator", "fixed_camera_confirmed", "roi_json", "source_url", "attribution", "license"}
            if set(form) - allowed or len(form.multi_items()) != len(form):
                raise VideoError(422, "invalid_upload", "Câmpuri necunoscute sau repetate în cererea video.")
            if form.get("fixed_camera_confirmed") not in ("true", "1"):
                raise VideoError(422, "fixed_camera_required", "Confirmă un cadru stabil: cameră fixă sau stabilizare documentată.")
            try:
                from pydantic import TypeAdapter
                operator = TypeAdapter(Operator).validate_python(form.get("operator"))
                data_mode = TypeAdapter(DataMode).validate_python(form.get("data_mode"))
                roi = json.loads(form["roi_json"]) if form.get("roi_json") else None
                from safecross.engine import validate_config
                validate_config({"roi": roi, "fixed_camera_confirmed": True})
            except (ValueError, ValidationError) as error:
                raise VideoError(422, "invalid_video_options", "Operatorul, modul de date sau poligonul ROI este invalid.") from error
            original_name = (upload.filename or "video").replace("\\", "/").rsplit("/", 1)[-1]
            extension = Path(original_name).suffix.lower()
            if extension not in VIDEO_EXTENSIONS:
                raise VideoError(422, "unsupported_video", "Folosește MP4, WebM, MOV, AVI sau MKV.")
            provenance = {key: str(form.get(key, "")).strip() for key in ("source_url", "attribution", "license")}
            if any(len(value) > 4000 for value in provenance.values()):
                raise VideoError(422, "invalid_provenance", "Descrierea provenienței este prea lungă.")
            if provenance["source_url"]:
                try:
                    parsed = urlsplit(provenance["source_url"])
                except ValueError as error:
                    raise VideoError(422, "invalid_provenance", "URL-ul sursei este invalid.") from error
                if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
                    raise VideoError(422, "invalid_provenance", "Sursa trebuie să fie un URL HTTP(S), fără credențiale.")
            job_id, source_name = uuid4().hex, "source" + extension
            folder = jobs.folder(job_id)
            folder.mkdir(parents=True, exist_ok=False)
            source_path = folder / source_name
            size = 0
            with source_path.open("xb") as output:
                while chunk := await upload.read(1024 * 1024):
                    size += len(chunk)
                    if size > LIMITS["max_upload_bytes"]:
                        raise VideoError(413, "video_too_large", "Clipul depășește limita locală de 64 MiB.")
                    output.write(chunk)
            if size == 0:
                raise VideoError(422, "empty_video", "Fișierul video este gol.")
            job = jobs.submit(job_id, source_name, original_name, data_mode, operator, roi, provenance)
            accepted = True
            return JSONResponse(status_code=202, content=job)
    except HTTPException as error:
        if overflow:
            raise VideoError(413, "video_too_large", "Clipul depășește limita locală de 64 MiB.") from error
        raise
    except OSError as error:
        raise VideoError(503, "video_storage_unavailable", "Clipul nu a putut fi salvat local.") from error
    finally:
        if not accepted:
            jobs.slots.release()
            if source_path is not None:
                source_path.unlink(missing_ok=True)
            if folder is not None and folder.is_dir() and not any(folder.iterdir()):
                folder.rmdir()


@router.get("/api/v1/safecross/jobs/{job_id}", summary="Read saved progress/results, including prior operator decisions")
def job(job_id: str, request: Request):
    return get_jobs(request).get(job_id)


@router.get("/api/v1/safecross/jobs/{job_id}/media/{artifact}", summary="Source/preview, evidence frames, or annotated AVI download")
def media(job_id: str, artifact: str, request: Request):
    path = get_jobs(request).media(job_id, artifact)
    return FileResponse(path, filename=path.name if artifact == "annotated" else None, content_disposition_type="attachment" if artifact == "annotated" else "inline", headers={"X-Content-Type-Options": "nosniff"})


@router.post("/api/v1/safecross/jobs/{job_id}/candidates/{candidate_id}/review", summary="Review a video flag; never create an accident record")
def review(job_id: str, candidate_id: str, body: VideoReview, request: Request):
    return get_jobs(request).review(job_id, candidate_id, body.expected_version, body.operator, body.decision, body.note)


@router.get("/api/v1/safecross/jobs/{job_id}/export", summary="Export evidence, model/parameters, provenance and review history")
def export(job_id: str, request: Request):
    saved = get_jobs(request).get(job_id)
    if saved["status"] != "completed":
        raise VideoError(409, "video_not_completed", "Exportul este disponibil după terminarea analizei.")
    return JSONResponse(content=saved, headers={"Content-Disposition": f'attachment; filename="safecross-{saved["data_mode"]}-{job_id}.json"'})


async def video_error_handler(request, error):
    return JSONResponse(status_code=error.status, content={"detail": {"code": error.code, "message": error.message}})


def register_safecross(application):
    application.include_router(router)
    application.add_exception_handler(VideoError, video_error_handler)
    return application
