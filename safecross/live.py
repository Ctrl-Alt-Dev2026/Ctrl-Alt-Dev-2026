"""Bounded live frame sessions. No stored images, remote stream fetching, or accident writes."""

import base64
from dataclasses import dataclass, field
import os
import struct
import threading
import time
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from safecross.live_analytics import Analytics
from safecross.live_detector import LiveDetector, VisionError


MAX_FRAME_BYTES = 2 * 1024 * 1024
MAX_SESSIONS = 16
SESSION_TTL = 120
# Serverless hosts (Vercel) spread one viewer's requests over several instances, each with its own memory. With
# SAFEIASI_VISION_STATELESS=1 the session id also carries its configuration, so an instance that never saw the
# session recreates it (tracking starts again there). Deleted or expired sessions stay rejected where they were known.
STATELESS = os.environ.get("SAFEIASI_VISION_STATELESS") == "1"


class Crosswalk(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    id: str = Field(min_length=1, max_length=60, pattern=r"^[a-zA-Z0-9_-]+$")
    polygon: list[tuple[float, float]] = Field(min_length=3, max_length=12)

    @model_validator(mode="after")
    def validate_polygon(self):
        if any(not 0 <= value <= 1 for point in self.polygon for value in point):
            raise ValueError("Crosswalk coordinates must be normalized to 0..1")
        area = abs(sum(x * self.polygon[(i + 1) % len(self.polygon)][1] - self.polygon[(i + 1) % len(self.polygon)][0] * y for i, (x, y) in enumerate(self.polygon))) / 2
        if area < .0001:
            raise ValueError("Crosswalk polygon must have nonzero area")
        return self


class SessionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    camera_id: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    crosswalks: list[Crosswalk] = Field(default_factory=list, max_length=8)
    detection_region: Crosswalk | None = None

    @model_validator(mode="after")
    def unique_ids(self):
        if len({region.id for region in self.crosswalks}) != len(self.crosswalks):
            raise ValueError("Crosswalk ids must be unique")
        return self


def jpeg_dimensions(data):
    """Read SOF before decoding, so a compressed image cannot allocate a giant frame."""
    if not data.startswith(b"\xff\xd8"):
        raise VisionError(422, "invalid_frame", "Cadrul trebuie să fie JPEG.")
    index = 2
    try:
        while index < len(data):
            if data[index] != 0xff:
                break
            while data[index] == 0xff:
                index += 1
            marker = data[index]
            index += 1
            if marker in (0xd9, 0xda):
                break
            if marker == 0x01 or 0xd0 <= marker <= 0xd8:
                continue
            length = struct.unpack_from(">H", data, index)[0]
            if length < 2 or index + length > len(data):
                break
            if marker in (0xc0, 0xc1, 0xc2):
                height, width = struct.unpack_from(">HH", data, index + 3)
                if not 16 <= width <= 1920 or not 16 <= height <= 1080:
                    raise VisionError(413, "frame_dimensions", "Cadrul trebuie să aibă între 16×16 și 1920×1080 pixeli.")
                return width, height
            index += length
    except (IndexError, struct.error):
        pass
    raise VisionError(422, "invalid_frame", "Antetul JPEG este invalid sau nesuportat.")


@dataclass
class Session:
    config: SessionConfig
    analytics: Analytics = field(default_factory=Analytics)
    touched: float = field(default_factory=time.monotonic)
    sequence: int = -1
    media_time: float = -1


class LiveVision:
    def __init__(self, detector_factory=LiveDetector, stateless=None):
        self.sessions = {}
        self.stateless = STATELESS if stateless is None else stateless
        self.ended = set()
        self.lock = threading.Lock()
        self.inference_lock = threading.Lock()
        self.detector_factory, self.detector = detector_factory, None

    def create(self, config):
        with self.lock:
            now = time.monotonic()
            self._prune(now)
            key = uuid4().hex
            if self.stateless:
                key += "." + base64.urlsafe_b64encode(config.model_dump_json().encode()).decode().rstrip("=")
            self.sessions[key] = Session(config)
            return {"session_id": key, "expires_in_s": SESSION_TTL, "max_frame_bytes": MAX_FRAME_BYTES}

    def _prune(self, now):
        expired = {key for key, value in self.sessions.items() if now - value.touched >= SESSION_TTL}
        self._end(*expired)
        if len(self.sessions) >= MAX_SESSIONS:
            raise VisionError(429, "vision_session_limit", "Prea multe camere active. Închide o cameră și reîncearcă.")

    def _end(self, *keys):
        if len(self.ended) > 1024:
            self.ended.clear()
        for key in keys:
            self.sessions.pop(key, None)
            self.ended.add(key)

    def _restore(self, key):
        """Stateless mode: a session created on another instance, rebuilt from the configuration in its id."""
        if not self.stateless or key in self.ended:
            return None
        try:
            _, encoded = key.split(".", 1)
            config = SessionConfig.model_validate_json(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        except ValueError:  # no configuration, bad base64 or an invalid configuration
            return None
        self._prune(time.monotonic())
        self.sessions[key] = session = Session(config)
        return session

    def delete(self, key):
        with self.lock:
            self._end(key)

    def process(self, key, data, sequence, media_time):
        # Do not build a stale inference queue when a second viewer or client is faster.
        if not self.inference_lock.acquire(blocking=False):
            raise VisionError(429, "vision_busy", "Detectorul procesează alt cadru. Reîncearcă pe cadrul curent.")
        try:
            with self.lock:
                session = self.sessions.get(key) or self._restore(key)
                if session is None or time.monotonic() - session.touched > SESSION_TTL:
                    self._end(key)
                    raise VisionError(404, "vision_session_expired", "Sesiunea camerei a expirat. Reconectează analiza.")
                if sequence <= session.sequence or media_time <= session.media_time:
                    raise VisionError(409, "stale_frame", "Cadrul este vechi sau a fost deja analizat.")
                session.touched = time.monotonic()
            if len(data) > MAX_FRAME_BYTES:
                raise VisionError(413, "frame_too_large", "Cadrul depășește 2 MiB.")
            width, height = jpeg_dimensions(data)
            import cv2
            import numpy as np

            frame = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is None or frame.shape[:2] != (height, width):
                raise VisionError(422, "invalid_frame", "Cadrul JPEG nu poate fi decodat.")
            started = time.perf_counter()
            if self.detector is None:
                self.detector = self.detector_factory()
            region = session.config.detection_region
            if region is None:
                detections, model = self.detector.detect(frame)
            else:
                polygon = np.array([[round(x * (width - 1)), round(y * (height - 1))] for x, y in region.polygon], dtype=np.int32)
                left, top, rw, rh = cv2.boundingRect(polygon)
                if rw < 32 or rh < 32:
                    raise VisionError(422, "detection_region_small", "Zona de detecție este prea mică. Marchează o zonă mai largă a străzii.")
                detections, model = self.detector.detect(frame[top:top + rh, left:left + rw])
                for detection in detections:
                    detection["box"][0] += left
                    detection["box"][1] += top
                detections = [d for d in detections if cv2.pointPolygonTest(polygon, (d["box"][0] + d["box"][2] / 2, d["box"][1] + d["box"][3]), False) >= 0]
            detections, light, signals, reset = session.analytics.update(detections, frame, media_time, [region.model_dump() for region in session.config.crosswalks])
            session.sequence, session.media_time = sequence, media_time
            session.touched = time.monotonic()
            return {
                "sequence": sequence, "media_time": media_time, "width": width, "height": height,
                "detections": detections, "light": light, "signals": signals, "model": model,
                "inference_ms": round((time.perf_counter() - started) * 1000),
                "tracking_reset": reset, "incident_status": "unverified_signals_only",
            }
        finally:
            self.inference_lock.release()
