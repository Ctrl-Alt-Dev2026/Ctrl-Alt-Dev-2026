"""Bounded, local video observation pipeline with deterministic tracking and flags.

Image proximity is a review aid. It is not a confirmed traffic conflict, a physical
distance, a speed estimate, TTC, PET, an accident count, or a validated risk score.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import math
from pathlib import Path
from statistics import median
from typing import Any, Callable

from safecross.detector import COCO_LABELS, Detection, SafeCrossError, YoloXDetector, dependencies, intersection_over_union


DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[1] / "runtime/models/yolox_nano.onnx"
LIMITATIONS = [
    "Proximitatea în imagine nu demonstrează un conflict sau o coliziune în spațiul fizic.",
    "Nu sunt calculate viteze, distanțe în metri, TTC, PET sau probabilități de accident.",
    "Cadrul stabil este confirmat de operator (cameră fixă sau stabilizare declarată), fără validare automată a stabilității.",
    "Detecțiile pot lipsi sau pot fi false; ocluzia și tracking-ul simplu pot schimba identitățile.",
    "Asocierea euristică persoană/bicicletă sau motocicletă poate elimina și un pieton care se deplasează alături; operatorul verifică video-ul.",
    "Absența candidaților nu demonstrează siguranța locației; video-ul este eșantionat.",
    "Timpul este indexul cadrului împărțit la FPS-ul declarat; video cu FPS variabil necesită verificare.",
    "Nu se identifică persoane sau numere de înmatriculare; imaginile originale rămân date locale.",
]


def _number(config, key, default, minimum, maximum, integer=False):
    value = config.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SafeCrossError("config_invalid", f"Parametrul {key} trebuie să fie numeric și finit.")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise SafeCrossError("config_invalid", f"Parametrul {key} trebuie să fie numeric și finit.")
    if not minimum <= value <= maximum or (integer and int(value) != value):
        raise SafeCrossError("config_invalid", f"Parametrul {key} trebuie să fie în intervalul {minimum}–{maximum}.")
    return int(value) if integer else float(value)


def validate_config(config: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(config, dict) or config.get("fixed_camera_confirmed") is not True:
        raise SafeCrossError("fixed_camera_required", "Operatorul trebuie să confirme un cadru stabil: cameră fixă sau stabilizare declarată, fără validare automată.")
    roi = config.get("roi")
    if roi is not None:
        if not isinstance(roi, list) or not 3 <= len(roi) <= 12:
            raise SafeCrossError("config_invalid", "ROI trebuie să fie un poligon cu 3–12 puncte normalizate.")
        points = []
        for point in roi:
            if not isinstance(point, (list, tuple)) or len(point) != 2:
                raise SafeCrossError("config_invalid", "Un punct ROI conține două coordonate normalizate.")
            points.append([_number({"x": point[0]}, "x", 0, 0, 1), _number({"y": point[1]}, "y", 0, 0, 1)])
        area = abs(sum(points[index][0] * points[(index + 1) % len(points)][1] - points[(index + 1) % len(points)][0] * points[index][1] for index in range(len(points)))) / 2
        if area < .0001:
            raise SafeCrossError("config_invalid", "Poligonul ROI trebuie să aibă o suprafață nenulă.")
        roi = points
    return {
        "model_path": str(config.get("model_path", DEFAULT_MODEL_PATH)),
        "fixed_camera_confirmed": True, "roi": roi,
        "confidence_threshold": _number(config, "confidence_threshold", .35, .1, .95),
        "nms_threshold": _number(config, "nms_threshold", .45, .1, .9),
        "sample_fps": _number(config, "sample_fps", 5, 1, 10),
        "max_duration_seconds": _number(config, "max_duration_seconds", 120, 1, 120),
        "max_frames": _number(config, "max_frames", 600, 1, 600, integer=True),
        "proximity_threshold": _number(config, "proximity_threshold", .035, .005, .15),
        "min_consecutive_observations": _number(config, "min_consecutive_observations", 3, 2, 10, integer=True),
        "min_vehicle_motion_normalized": _number(config, "min_vehicle_motion_normalized", .01, .003, .05),
    }


def _center(bbox):
    return ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)


def image_gap(first, second, width, height) -> float:
    """Minimum rectangle separation divided by image diagonal, not ground distance."""
    dx = max(first[0] - second[2], second[0] - first[2], 0)
    dy = max(first[1] - second[3], second[1] - first[3], 0)
    return math.hypot(dx, dy) / math.hypot(width, height)


def _inside(point, polygon):
    """Even-odd test; points on a polygon boundary count as inside."""
    x, y = point
    result = False
    for index, first in enumerate(polygon):
        second = polygon[(index + 1) % len(polygon)]
        cross = (x - first[0]) * (second[1] - first[1]) - (y - first[1]) * (second[0] - first[0])
        if abs(cross) < 1e-10 and min(first[0], second[0]) <= x <= max(first[0], second[0]) and min(first[1], second[1]) <= y <= max(first[1], second[1]):
            return True
        if (first[1] > y) != (second[1] > y):
            crossing_x = (second[0] - first[0]) * (y - first[1]) / (second[1] - first[1]) + first[0]
            if x < crossing_x:
                result = not result
    return result


def in_roi(bbox, roi, width, height):
    # Ground-contact proxy, explicitly image coordinates, not a calibrated ground point.
    return roi is None or _inside(((bbox[0] + bbox[2]) / (2 * width), bbox[3] / height), roi)


@dataclass
class Track:
    track_id: str
    class_id: int
    last_s: float
    bbox: tuple
    observations: list[dict] = field(default_factory=list)
    gap_count: int = 0
    last_sample: int = 0


class SimpleTracker:
    """Greedy same-class association; no interpolation and no physical-motion model."""

    def __init__(self, width: int, height: int, max_gap_s: float = .8):
        self.width, self.height = width, height
        self.max_gap_s = max_gap_s
        self.tracks: dict[str, Track] = {}
        self.counter = 0

    def update(self, detections: list[Detection], time_s: float, frame_index: int, sample_index: int) -> list[dict]:
        eligible = [track for track in self.tracks.values() if time_s - track.last_s <= self.max_gap_s + 1e-8]
        pairs = []
        for track in eligible:
            for index, detection in enumerate(detections):
                if track.class_id != detection.class_id:
                    continue
                previous_center, current_center = _center(track.bbox), _center(detection.bbox)
                distance = math.dist(previous_center, current_center) / math.hypot(self.width, self.height)
                overlap = intersection_over_union(track.bbox, detection.bbox)
                if overlap >= .1 or distance <= .06:
                    pairs.append((distance + (1 - overlap) * .03, track.track_id, index))
        matched_tracks, matched_detections, assignments = set(), set(), {}
        for _, track_id, index in sorted(pairs):
            if track_id not in matched_tracks and index not in matched_detections:
                matched_tracks.add(track_id)
                matched_detections.add(index)
                assignments[index] = self.tracks[track_id]
        result = []
        for index, detection in enumerate(detections):
            track = assignments.get(index)
            if track is None:
                if len(self.tracks) >= 2000:
                    raise SafeCrossError("too_many_tracks", "Prea multe track-uri; scurtează clipul sau restrânge zona filmată.")
                self.counter += 1
                track = Track(f"track-{self.counter:05d}", detection.class_id, time_s, detection.bbox, last_sample=sample_index)
                self.tracks[track.track_id] = track
            elif sample_index - track.last_sample > 1:
                track.gap_count += 1
            observation = {
                "track_id": track.track_id, "label": detection.label, "kind": detection.kind,
                "coco_class_id": detection.class_id, "confidence": round(detection.confidence, 5),
                "bbox": [round(value, 2) for value in detection.bbox],
            }
            track.last_s, track.bbox, track.last_sample = time_s, detection.bbox, sample_index
            track.observations.append({"time_s": round(time_s, 5), "frame_index": frame_index, **observation})
            result.append(observation)
        return result

    def summary(self):
        return [{
            "track_id": track.track_id, "label": COCO_LABELS[track.class_id],
            "kind": "person" if track.class_id == 0 else "vehicle", "coco_class_id": track.class_id,
            "first_s": track.observations[0]["time_s"], "last_s": track.observations[-1]["time_s"],
            "observation_count": len(track.observations), "gap_count": track.gap_count,
            "identity_verified": False,
        } for track in self.tracks.values()]


class CandidateCollector:
    """One window per track pair; persistence suppresses isolated-frame noise."""

    def __init__(self, width, height, config):
        self.width, self.height, self.config = width, height, config
        self.windows: dict[tuple, dict] = {}
        self.completed: list[dict] = []
        self.discarded_isolated = 0
        self.discarded_stationary = 0
        self.discarded_possible_rider = 0

    def update(self, objects, time_s, frame_index, sample_index):
        present = set()
        changed = []
        people = [obj for obj in objects if obj["kind"] == "person" and in_roi(obj["bbox"], self.config["roi"], self.width, self.height)]
        vehicles = [obj for obj in objects if obj["kind"] == "vehicle" and in_roi(obj["bbox"], self.config["roi"], self.width, self.height)]
        for person in people:
            for vehicle in vehicles:
                gap = image_gap(person["bbox"], vehicle["bbox"], self.width, self.height)
                if gap > self.config["proximity_threshold"]:
                    continue
                key = person["track_id"], vehicle["track_id"]
                present.add(key)
                window = self.windows.get(key)
                if window is None:
                    window = {"start_s": round(time_s, 5), "end_s": round(time_s, 5), "observations": 0, "consecutive": 0, "max_consecutive": 0, "last_sample": sample_index - 1, "minimum_image_gap": float("inf"), "vehicle_centers": [], "possible_rider_observations": []}
                    self.windows[key] = window
                window["consecutive"] = window["consecutive"] + 1 if sample_index - window["last_sample"] == 1 else 1
                window["max_consecutive"] = max(window["max_consecutive"], window["consecutive"])
                window["last_sample"], window["end_s"] = sample_index, round(time_s, 5)
                window["observations"] += 1
                window["vehicle_centers"].append(_center(vehicle["bbox"]))
                if vehicle["label"] in ("bicycle", "motorcycle"):
                    person_box, vehicle_box = person["bbox"], vehicle["bbox"]
                    foot_x, foot_y = (person_box[0] + person_box[2]) / 2, person_box[3]
                    if vehicle_box[0] <= foot_x <= vehicle_box[2] and vehicle_box[1] <= foot_y <= vehicle_box[3]:
                        window["possible_rider_observations"].append((_center(person_box), _center(vehicle_box)))
                if gap < window["minimum_image_gap"]:
                    window.update({
                        "minimum_image_gap": gap, "representative_s": round(time_s, 5), "frame_index": frame_index,
                        "person": dict(person), "vehicle": dict(vehicle),
                    })
                    changed.append(key)
        for key in list(self.windows):
            if key not in present and time_s - self.windows[key]["end_s"] > .6:
                self._finish(key)
        return changed

    def _finish(self, key):
        window = self.windows.pop(key)
        if window["max_consecutive"] < self.config["min_consecutive_observations"]:
            self.discarded_isolated += 1
            return
        centers = window["vehicle_centers"]
        sample_count = max(1, len(centers) // 3)
        first = tuple(median(point[axis] for point in centers[:sample_count]) for axis in (0, 1))
        last = tuple(median(point[axis] for point in centers[-sample_count:]) for axis in (0, 1))
        displacement = math.dist(first, last) / math.hypot(self.width, self.height)
        if displacement < self.config["min_vehicle_motion_normalized"]:
            self.discarded_stationary += 1
            return
        if self._possible_rider(window):
            self.discarded_possible_rider += 1
            return
        if len(self.completed) >= 200:
            raise SafeCrossError("too_many_candidates", "Peste 200 de interacțiuni candidate; scurtează clipul sau restrânge ROI.")
        self.completed.append({
            "candidate_id": f"candidate-{len(self.completed) + 1:04d}",
            "start_s": window["start_s"], "end_s": window["end_s"],
            "representative_s": window["representative_s"], "frame_index": window["frame_index"],
            "person_track_id": key[0], "vehicle_track_id": key[1],
            "reason": "Apropiere persistentă a bounding box-urilor în imagine" + (" în ROI-ul operatorului." if self.config["roi"] else "."),
            "reason_codes": ["persistent_image_bbox_proximity", "vehicle_image_displacement"] + (["both_footpoints_in_user_roi"] if self.config["roi"] else []),
            "image_gap_normalized": round(window["minimum_image_gap"], 6),
            "threshold_normalized": self.config["proximity_threshold"],
            "proximity_observation_count": window["observations"],
            "max_consecutive_observations": window["max_consecutive"],
            "vehicle_image_displacement_normalized": round(displacement, 6),
            "vehicle_motion_threshold_normalized": self.config["min_vehicle_motion_normalized"],
            "evidence": {"time_s": window["representative_s"], "frame_index": window["frame_index"], "person": window["person"], "vehicle": window["vehicle"]},
            "review_status": "pending", "confirmed_conflict": False,
            "snapshot": f"candidate-{len(self.completed) + 1:04d}.jpg",
            "limitations": ["Perspectiva și ocluzia pot produce apropieri doar aparente.", "Identitățile track-urilor nu sunt validate de operator."],
        })

    def _possible_rider(self, window):
        """Conservative same-object grouping; this is not a person identity claim.

        A rider is represented by TWO COCO detections. Suppress that pairing only
        after at least three geometrically supported observations that move
        together and retain a stable relative image offset. Ambiguous cases stay
        pending for human review; a pedestrian alongside a bike can be missed.
        """
        observations = window["possible_rider_observations"]
        if len(observations) < 3:
            return False
        first_person, first_vehicle = observations[0]
        last_person, last_vehicle = observations[-1]
        person_vector = tuple(last_person[axis] - first_person[axis] for axis in (0, 1))
        vehicle_vector = tuple(last_vehicle[axis] - first_vehicle[axis] for axis in (0, 1))
        vehicle_length = math.hypot(*vehicle_vector)
        if vehicle_length <= 1e-8 or math.dist(person_vector, vehicle_vector) / vehicle_length > .4:
            return False
        diagonal = math.hypot(self.width, self.height)
        offsets = [(person[0] - vehicle[0], person[1] - vehicle[1]) for person, vehicle in observations]
        maximum_offset_change = max(math.dist(offsets[0], offset) for offset in offsets)
        return maximum_offset_change / diagonal <= .02

    def finish(self):
        for key in list(self.windows):
            self._finish(key)
        return self.completed


def _draw(frame, objects, roi, cv2, np):
    canvas = frame.copy()
    height, width = canvas.shape[:2]
    if roi:
        polygon = np.array([[int(x * width), int(y * height)] for x, y in roi], dtype=np.int32)
        cv2.polylines(canvas, [polygon], True, (0, 210, 255), 2)
    for obj in objects:
        left, top, right, bottom = [int(value) for value in obj["bbox"]]
        color = (70, 210, 100) if obj["kind"] == "person" else (255, 165, 70)
        cv2.rectangle(canvas, (left, top), (right, bottom), color, 2)
        cv2.putText(canvas, f"{obj['track_id']} {obj['label']} {obj['confidence']:.2f}", (left, max(18, top - 6)), cv2.FONT_HERSHEY_SIMPLEX, .45, color, 1, cv2.LINE_AA)
    cv2.rectangle(canvas, (0, max(0, height - 28)), (width, height), (20, 20, 20), -1)
    cv2.putText(canvas, "SafeCross - IMAGE observations only - HUMAN REVIEW REQUIRED", (8, height - 9), cv2.FONT_HERSHEY_SIMPLEX, .42, (255, 255, 255), 1, cv2.LINE_AA)
    return canvas


def _small(frame, cv2):
    height, width = frame.shape[:2]
    ratio = min(1.0, 1280 / width, 720 / height)
    target_width, target_height = max(2, int(width * ratio) // 2 * 2), max(2, int(height * ratio) // 2 * 2)
    return cv2.resize(frame, (target_width, target_height), interpolation=cv2.INTER_AREA)


def analyze_video(input_path: str | Path, output_dir: str | Path, config: dict[str, Any], progress: Callable[[dict], None] | None = None, detector=None) -> dict:
    """Analyze at most 120 s/600 sampled frames and return JSON-compatible evidence.

    Artifacts are local JPEGs and a sampled MJPEG AVI. `frames` boxes refer to the
    ORIGINAL source dimensions, allowing a browser canvas to overlay the source.
    Injecting a detector is intended for explicit synthetic tests only.
    """
    settings = validate_config(config)
    cv2, np = dependencies()
    source, target = Path(input_path), Path(output_dir)
    if not source.is_file():
        raise SafeCrossError("video_missing", "Fișierul video local nu există.")
    target.mkdir(parents=True, exist_ok=True)
    if any((target / name).exists() for name in ("annotated.avi", "poster.jpg")):
        raise SafeCrossError("output_exists", "Directorul de rezultate conține deja o analiză; folosește un job nou.")
    capture = cv2.VideoCapture(str(source))
    writer = None
    created: list[Path] = []
    try:
        if not capture.isOpened():
            raise SafeCrossError("video_unreadable", "OpenCV nu poate deschide fișierul video.")
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        width, height = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        declared_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if not math.isfinite(fps) or not 1 <= fps <= 120 or min(width, height) < 16 or max(width, height) > 4096 or width * height > 2_073_600:
            raise SafeCrossError("video_metadata_invalid", "Dimensiuni sau FPS video nesuportate; reexportă un clip standard.")
        declared_duration = declared_count / fps if declared_count > 0 else None
        if declared_duration is not None and declared_duration > settings["max_duration_seconds"] + .001:
            raise SafeCrossError("video_too_long", "Clipul depășește durata maximă configurată; scurtează-l înainte de import.")
        effective_sample_fps = min(fps, settings["sample_fps"])
        if declared_duration is not None and math.ceil(declared_duration * effective_sample_fps - 1e-8) > settings["max_frames"]:
            raise SafeCrossError("too_many_frames", "Clipul necesită prea multe cadre eșantionate; scade sample_fps sau scurtează clipul.")
        detector = detector or YoloXDetector(settings["model_path"], settings["confidence_threshold"], settings["nms_threshold"])
        tracker = SimpleTracker(width, height, max_gap_s=max(.8, 1.5 / effective_sample_fps))
        collector = CandidateCollector(width, height, settings)
        frames, frame_index, sampled = [], 0, 0
        while True:
            available, frame = capture.read()
            if not available:
                break
            time_s = frame_index / fps
            if time_s >= settings["max_duration_seconds"] - 1e-8:
                raise SafeCrossError("video_too_long", "Durata decodată depășește limita; analiza nu a fost trunchiată în tăcere.")
            if frame_index >= round(sampled * fps / effective_sample_fps):
                if sampled >= settings["max_frames"]:
                    raise SafeCrossError("too_many_frames", "Limita de cadre a fost depășită; analiza nu a fost trunchiată.")
                if frame.shape[:2] != (height, width):
                    raise SafeCrossError("video_dimensions_changed", "Dimensiunea cadrelor se modifică în clip; reexportă filmarea.")
                detections = detector.detect(frame)
                if len(detections) > 80 or any(not isinstance(item, Detection) or item.class_id not in COCO_LABELS or not 0 <= item.confidence <= 1 or not all(math.isfinite(value) for value in item.bbox) or not (0 <= item.bbox[0] < item.bbox[2] <= width and 0 <= item.bbox[1] < item.bbox[3] <= height) for item in detections):
                    raise SafeCrossError("detections_invalid", "Detectorul a produs observații invalide.")
                objects = tracker.update(detections, time_s, frame_index, sampled)
                frames.append({"time_s": round(time_s, 5), "frame_index": frame_index, "objects": objects})
                collector.update(objects, time_s, frame_index, sampled)
                annotated = _small(_draw(frame, objects, settings["roi"], cv2, np), cv2)
                if writer is None:
                    artifact = target / "annotated.avi"
                    created.append(artifact)
                    writer = cv2.VideoWriter(str(artifact), cv2.VideoWriter_fourcc(*"MJPG"), effective_sample_fps, (annotated.shape[1], annotated.shape[0]))
                    if not writer.isOpened():
                        raise SafeCrossError("video_writer_failed", "OpenCV nu poate crea redarea MJPEG AVI.")
                    poster = target / "poster.jpg"
                    created.append(poster)
                    if not cv2.imwrite(str(poster), annotated):
                        raise SafeCrossError("artifact_write_failed", "Imaginea poster nu poate fi salvată.")
                writer.write(annotated)
                sampled += 1
                if progress and (sampled == 1 or sampled % 5 == 0):
                    progress({"stage": "processing", "processed_frames": sampled, "time_s": round(time_s, 3), "progress": min(.95, frame_index / declared_count) if declared_count > 0 else None})
            frame_index += 1
        if frame_index == 0:
            raise SafeCrossError("video_empty", "Clipul nu conține cadre care pot fi decodate.")
        if declared_count > 0 and frame_index < declared_count - max(2, int(fps * .15)):
            raise SafeCrossError("video_incomplete", "Decodarea s-a oprit înainte de finalul declarat; rezultatul nu este publicat parțial.")
        candidates = collector.finish()
        writer.release()
        writer = None
        # Re-read only representative frames so no full-resolution frame buffer is retained.
        for candidate in candidates:
            if not capture.set(cv2.CAP_PROP_POS_FRAMES, candidate["frame_index"]):
                raise SafeCrossError("evidence_seek_failed", "Codec-ul nu permite poziționarea exactă la cadrul de evidență.")
            available, frame = capture.read()
            if not available or abs(capture.get(cv2.CAP_PROP_POS_FRAMES) - candidate["frame_index"] - 1) > .1:
                raise SafeCrossError("evidence_unreadable", "Cadrul reprezentativ nu poate fi recitit.")
            image = _small(_draw(frame, [candidate["evidence"]["person"], candidate["evidence"]["vehicle"]], settings["roi"], cv2, np), cv2)
            snapshot = target / candidate["snapshot"]
            created.append(snapshot)
            if not cv2.imwrite(str(snapshot), image):
                raise SafeCrossError("artifact_write_failed", "Cadrul de evidență nu poate fi salvat.")
        public_settings = {key: value for key, value in settings.items() if key != "model_path"}
        warnings = list(LIMITATIONS)
        if any(len(frame["objects"]) >= 80 for frame in frames):
            warnings.append("Cel puțin un cadru a atins limita de 80 de detecții; observațiile pot fi incomplete.")
        source_hash = sha256()
        with source.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                source_hash.update(chunk)
        result = {
            "schema_version": "safecross-1.0", "analysis_kind": "image_proximity_candidates",
            "generated_at": datetime.now(timezone.utc).isoformat(), "response_origin": "local_video_analysis",
            "video": {"width": width, "height": height, "fps": fps, "duration_s": round(frame_index / fps, 5), "decoded_frame_count": frame_index, "declared_frame_count": declared_count, "time_base": "frame_index/source_fps"},
            "source_sha256": source_hash.hexdigest(),
            "model": dict(getattr(detector, "metadata", {"name": "injected-synthetic-detector", "synthetic": True})),
            "parameters": public_settings | {"view_requirement": "fixed_or_documented_stabilized_view", "stability_automatically_verified": False, "effective_sample_fps": effective_sample_fps, "bbox_coordinates": "original_source_pixels_xyxy", "proximity_measure": "minimum_bbox_gap/image_diagonal", "tracker": "deterministic-greedy-same-COCO-class", "track_max_gap_s": tracker.max_gap_s, "rider_suppression": {"minimum_supported_observations": 3, "maximum_relative_motion_error": .4, "maximum_offset_change_normalized": .02, "classes": ["bicycle", "motorcycle"]}},
            "frames": frames, "sampled_frame_count": sampled, "tracks": tracker.summary(),
            "candidates": candidates, "candidate_count": len(candidates), "limitations": warnings,
            "screening": {"discarded_isolated_windows": collector.discarded_isolated, "discarded_stationary_vehicle_windows": collector.discarded_stationary, "discarded_possible_rider_windows": collector.discarded_possible_rider},
            "artifacts": {"poster": "poster.jpg", "annotated_video": "annotated.avi", "annotated_video_format": "MJPEG AVI; sampled playback; source overlay uses original pixels", "snapshots": [candidate["snapshot"] for candidate in candidates]},
            "review_required": True, "calibration": "uncalibrated", "safety_certification": False,
        }
        if progress:
            progress({"stage": "complete", "processed_frames": sampled, "progress": 1.0})
        return result
    except Exception:
        if writer is not None:
            writer.release()
            writer = None
        for path in created:
            path.unlink(missing_ok=True)
        raise
    finally:
        capture.release()
        if writer is not None:
            writer.release()
