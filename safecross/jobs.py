"""Persisted single-process video jobs; only operator review confirms a flag."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading

from safecross.setup import MODEL_SHA256, MODEL_URL


LIMITS = {"max_upload_bytes": 64 * 1024 * 1024, "max_duration_s": 120, "max_video_pixels": 2_073_600, "max_frames": 600, "sample_fps": 5, "max_queued_jobs": 3}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".avi", ".mkv"}
_LOCK = threading.RLock()


class VideoError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message
        super().__init__(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def _atomic(path, value):
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False) as output:
            temporary = Path(output.name)
            json.dump(value, output, ensure_ascii=False, allow_nan=False, indent=2)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    except (OSError, ValueError, UnicodeError) as error:
        raise VideoError(503, "video_storage_unavailable", "Analiza nu a putut fi salvată.") from error
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def readiness(model_path):
    dependencies = all(importlib.util.find_spec(name) is not None for name in ("cv2", "numpy", "python_multipart"))
    timing_ready = shutil.which("ffprobe") is not None
    path = Path(model_path)
    try:
        valid_model = path.is_file() and path.stat().st_size < 8 * 1024 * 1024 and hashlib.sha256(path.read_bytes()).hexdigest() == MODEL_SHA256
    except OSError:
        valid_model = False
    return {
        "available": dependencies and valid_model and timing_ready, "model_ready": valid_model,
        "timing_ready": timing_ready,
        "dependencies_ready": dependencies, "model": {"name": "YOLOX Nano ONNX 0.1.1rc0", "sha256": MODEL_SHA256, "source_url": MODEL_URL},
        "limits": LIMITS,
        "message": (
            "Instalează requirements-safecross.txt și rulează python -m safecross.setup; pornirea API-ului nu descarcă nimic."
            if not (dependencies and valid_model) else
            "FFprobe lipsește; instalează FFmpeg local și adaugă executabilele în PATH pentru verificarea timestampurilor."
            if not timing_ready else "Procesare video locală disponibilă."
        ),
    }


class VideoJobs:
    def __init__(self, directory, model_path, runner=None):
        self.directory, self.model_path = Path(directory).resolve(), Path(model_path).resolve()
        repository = Path(__file__).resolve().parents[1]
        if any(self.directory.is_relative_to(repository / name) for name in ("false_data", "ai/benchmarks", ".git")):
            raise VideoError(503, "protected_video_directory", "Alege un director de lucru separat de fixture-urile comune.")
        self.runner = runner
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="safecross")
        self.slots = threading.BoundedSemaphore(LIMITS["max_queued_jobs"])
        # Interrupted jobs are explicitly failed; saved results are never replayed as new inference.
        if self.directory.exists():
            for path in self.directory.glob("*/job.json"):
                try:
                    saved = self.get(path.parent.name)
                    if saved["status"] in ("queued", "running"):
                        saved.update(status="failed", error={"code": "analysis_interrupted", "message": "Procesarea a fost întreruptă; încarcă din nou clipul."}, updated_at=now())
                        _atomic(path, saved)
                except VideoError:
                    continue

    def folder(self, job_id):
        if not re.fullmatch(r"[0-9a-f]{32}", job_id):
            raise VideoError(404, "video_not_found", "Analiză video inexistentă.")
        folder = self.directory / job_id
        if folder.resolve().parent != self.directory:
            raise VideoError(404, "video_not_found", "Analiză video inexistentă.")
        return folder

    def get(self, job_id):
        with _LOCK:
            try:
                job = json.loads((self.folder(job_id) / "job.json").read_text(encoding="utf-8"))
                if not isinstance(job, dict) or job["job_id"] != job_id or job["data_mode"] not in ("synthetic", "observed"):
                    raise ValueError("invalid job identity")
                if job["status"] not in ("queued", "running", "completed", "failed") or type(job["version"]) is not int or job["version"] < 1:
                    raise ValueError("invalid job state")
                if type(job["progress"]) not in (int, float) or not math.isfinite(job["progress"]) or not 0 <= job["progress"] <= 1:
                    raise ValueError("invalid job progress")
                if not re.fullmatch(r"source\.(mp4|webm|mov|avi|mkv)", job["source_name"]):
                    raise ValueError("invalid source path")
                if not isinstance(job["reviews"], dict) or not isinstance(job["history"], list):
                    raise ValueError("invalid review history")
                if not all(isinstance(job[key], str) for key in ("operator", "original_name", "created_at", "updated_at")):
                    raise ValueError("invalid job metadata")
                if job["status"] == "completed":
                    result = job["result"]
                    if not isinstance(result, dict) or not isinstance(result["video"], dict) or not isinstance(result["frames"], list) or not isinstance(result["candidates"], list):
                        raise ValueError("invalid completed result")
                    candidates = result["candidates"]
                    candidate_ids = {candidate["candidate_id"] for candidate in candidates}
                    if len(candidate_ids) != len(candidates) or any(not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value) for value in candidate_ids):
                        raise ValueError("invalid video candidate identity")
                    if not set(job["reviews"]) <= candidate_ids:
                        raise ValueError("review references unknown candidate")
                elif job["result"] is not None:
                    raise ValueError("partial result must not be published")
                json.dumps(job, allow_nan=False, ensure_ascii=False).encode("utf-8")
                return job | {"response_origin": "stored_analysis"}
            except FileNotFoundError as error:
                raise VideoError(404, "video_not_found", "Analiză video inexistentă.") from error
            except (OSError, ValueError, KeyError, TypeError, UnicodeError) as error:
                raise VideoError(503, "video_storage_unavailable", "Analiza salvată nu poate fi citită.") from error

    def reserve(self):
        if not self.slots.acquire(blocking=False):
            raise VideoError(429, "video_queue_full", "Coada locală este ocupată; așteaptă terminarea analizelor curente.")

    def submit(self, job_id, source_name, original_name, data_mode, operator, roi, provenance):
        job = {
            "job_id": job_id, "status": "queued", "progress": 0.0, "stage": "queued", "version": 1,
            "data_mode": data_mode, "operator": operator, "source_name": source_name, "original_name": original_name,
            "created_at": now(), "updated_at": now(), "error": None, "result": None, "reviews": {}, "history": [],
            "provenance": provenance, "fixed_camera_confirmed": True, "roi": roi,
            "publication_status": "not_published", "record_type": "video_observation",
            "source_sha256": hashlib.sha256((self.folder(job_id) / source_name).read_bytes()).hexdigest(),
        }
        with _LOCK:
            _atomic(self.folder(job_id) / "job.json", job)
        self.executor.submit(self._run, job_id)
        return job | {"response_origin": "stored_analysis"}

    def _update(self, job_id, **changes):
        with _LOCK:
            job = self.get(job_id)
            job.update(changes, updated_at=now())
            _atomic(self.folder(job_id) / "job.json", job)

    def _run(self, job_id):
        try:
            self._update(job_id, status="running", stage="validating_timing")
            job, folder = self.get(job_id), self.folder(job_id)
            timing = None
            if self.runner is None:
                from safecross.engine import analyze_video
                from safecross.timing import verify_video_timing
                timing = verify_video_timing(folder / job["source_name"])
                runner = analyze_video
            else:
                runner = self.runner
            config = {
                "model_path": str(self.model_path), "roi": job["roi"], "fixed_camera_confirmed": True,
                "sample_fps": LIMITS["sample_fps"], "max_frames": LIMITS["max_frames"],
                "max_duration_seconds": LIMITS["max_duration_s"], "max_video_pixels": LIMITS["max_video_pixels"],
            }
            result = runner(folder / job["source_name"], folder, config, lambda progress: self._update(job_id, progress=min(.94, float(progress.get("progress") or 0)), stage="detecting"))
            if timing is not None:
                video = result["video"]
                if video["decoded_frame_count"] != timing["frame_count"] or abs(video["fps"] - timing["fps"]) > 1e-6 or video["width"] != timing["width"] or video["height"] != timing["height"]:
                    raise VideoError(422, "video_timing_decoder_mismatch", "Decoderul și verificarea timestampurilor nu corespund; reexportă un clip CFR standard.")
                result["timing"] = timing
            self._update(job_id, progress=.95, stage="preparing_preview")
            preview = self._preview(folder / job["source_name"], folder)
            result["preview_available"] = preview
            result["data_mode"] = job["data_mode"]
            result["publication_status"] = "not_published"
            result["processing_mode"] = "local_video_inference"
            result["source_sha256"] = job["source_sha256"]
            self._update(job_id, status="completed", progress=1.0, stage="completed", result=result)
        except Exception as error:
            code = getattr(error, "code", "video_processing_failed")
            message = getattr(error, "message", "Procesarea clipului a eșuat; verifică formatul, durata și dependențele locale.")
            try:
                self._update(job_id, status="failed", progress=0.0, stage="failed", result=None, error={"code": code, "message": message})
            except VideoError:
                pass
        finally:
            self.slots.release()

    @staticmethod
    def _preview(source, folder):
        executable = shutil.which("ffmpeg")
        if executable is None:
            return False
        destination = folder / "preview.mp4"
        try:
            completed = subprocess.run(
                [executable, "-nostdin", "-v", "error", "-i", str(source), "-t", str(LIMITS["max_duration_s"]),
                 "-vf", "scale=trunc(min(1280\\,iw)/2)*2:-2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-an", "-map_metadata", "-1", "-movflags", "+faststart", "-y", str(destination)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=45,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return completed.returncode == 0 and destination.is_file() and destination.stat().st_size > 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    def review(self, job_id, candidate_id, expected_version, operator, decision, note):
        with _LOCK:
            job = self.get(job_id)
            if job["status"] != "completed":
                raise VideoError(409, "video_not_completed", "Verificarea este disponibilă după terminarea analizei.")
            if job["version"] != expected_version:
                raise VideoError(409, "video_version_conflict", "Analiza a fost verificată între timp; recitește versiunea curentă.")
            if candidate_id not in {c["candidate_id"] for c in job["result"]["candidates"]}:
                raise VideoError(404, "video_candidate_not_found", "Interacțiune candidat inexistentă.")
            reviewed = {"decision": decision, "operator": operator, "note": note, "at": now(), "candidate_id": candidate_id}
            job["reviews"][candidate_id] = reviewed
            job["version"] += 1
            job["history"].append(reviewed | {"version": job["version"]})
            _atomic(self.folder(job_id) / "job.json", job)
            return job

    def media(self, job_id, artifact):
        job = self.get(job_id)
        folder = self.folder(job_id)
        if artifact == "source":
            filename = "preview.mp4" if (job.get("result") or {}).get("preview_available") else job["source_name"]
        elif artifact == "annotated":
            filename = "annotated.avi"
        elif artifact == "poster.jpg" or re.fullmatch(r"[A-Za-z0-9_-]+\.jpg", artifact):
            filename = artifact
        else:
            raise VideoError(404, "video_media_not_found", "Fișier media inexistent.")
        path = folder / filename
        if not path.is_file() or path.is_symlink():
            raise VideoError(404, "video_media_not_found", "Fișier media inexistent.")
        if artifact != "source" and job["status"] != "completed":
            raise VideoError(409, "video_not_completed", "Rezultatele parțiale nu sunt publicate.")
        return path
