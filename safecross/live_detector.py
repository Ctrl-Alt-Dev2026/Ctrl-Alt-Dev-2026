"""Traffic detection with a conditional, cropped tram classification pass."""

import importlib.util
import os
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "runtime/models/traffic-world.pt"
TRAFFIC_MODEL_PATH = ROOT / "runtime/models/yolo11s.pt"
TRAFFIC_CLASSES = {0: "person", 1: "bicycle", 2: "car", 3: "motorcycle", 5: "bus", 6: "train", 7: "truck"}
LABELS = ("person", "car", "bus", "tram", "rail_vehicle", "truck", "motorcycle", "bicycle")
PROMPTS = ("person", "car", "bus", "tram streetcar", "truck", "motorcycle", "bicycle")


class VisionError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def model_path():
    return Path(os.environ.get("SAFEIASI_VISION_MODEL", MODEL_PATH)).resolve()


def traffic_model_path():
    return Path(os.environ.get("SAFEIASI_VISION_TRAFFIC_MODEL", TRAFFIC_MODEL_PATH)).resolve()


def readiness():
    dependencies = all(importlib.util.find_spec(name) is not None for name in ("ultralytics", "torch", "cv2", "numpy"))
    weights_ready = model_path().is_file() and traffic_model_path().is_file()
    ready = weights_ready and dependencies
    return {
        "available": ready, "model": "YOLO11s + YOLO-World trams", "labels": list(LABELS),
        "dependencies_ready": dependencies, "model_ready": weights_ready,
        "message": "Detector local pregătit." if ready else "Detector indisponibil. Rulează: pip install -r requirements-vision.txt, apoi python -m safecross.live_setup.",
        "incident_detection": "temporal_heuristics_unvalidated", "lighting": "image_luminance_not_lux",
    }


class LiveDetector:
    """Access is serialized by LiveVision; no model state is shared concurrently."""

    def __init__(self):
        status = readiness()
        if not status["available"]:
            raise VisionError(503, "vision_not_ready", status["message"])
        os.environ.setdefault("YOLO_CONFIG_DIR", str(ROOT / "runtime/ultralytics"))
        os.environ["YOLO_AUTOINSTALL"] = "false"
        os.environ["YOLO_OFFLINE"] = "true"
        try:
            import torch
            from ultralytics import YOLO
            from ultralytics import settings

            settings.update({"sync": False, "weights_dir": str(ROOT / "runtime/models"), "runs_dir": str(ROOT / "runtime/runs")})
            torch.set_num_threads(min(4, os.cpu_count() or 1))
            self.model = None  # Most frames have no bus/rail candidate; avoid loading/running CLIP-derived detection.
            self.traffic = YOLO(str(traffic_model_path()))
            if any(self.traffic.names.get(key) != value for key, value in TRAFFIC_CLASSES.items()):
                raise ValueError("Unexpected traffic classes")
            self.device = os.environ.get("SAFEIASI_VISION_DEVICE", "0" if torch.cuda.is_available() else "cpu")
            self.imgsz = int(os.environ.get("SAFEIASI_VISION_IMGSZ", "960"))
            if self.imgsz not in (640, 960, 1280):
                raise ValueError("SAFEIASI_VISION_IMGSZ must be 640, 960 or 1280")
        except Exception as error:
            raise VisionError(503, "vision_model_invalid", "Modelul local nu poate fi încărcat. Rulează python -m safecross.live_setup; verifică dispozitivul configurat.") from error

    def detect(self, frame):
        import cv2
        import numpy as np
        import torch

        # FastAPI can execute each frame on a different worker thread. Apply the CPU
        # limit in that thread too; constructor-only settings do not cover new workers.
        if self.device == "cpu":
            torch.set_num_threads(4)

        # Improve local contrast for detection only. Lighting always uses the original.
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        enhanced = float(np.median(gray)) < 65
        image = frame
        if enhanced:
            lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
            lab[:, :, 0] = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(lab[:, :, 0])
            image = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        started = time.perf_counter()
        try:
            traffic = self.traffic.predict(
                image, imgsz=self.imgsz, conf=.35, iou=.45, max_det=150,
                classes=list(TRAFFIC_CLASSES), device=self.device, verbose=False,
            )[0]
        except Exception as error:
            raise VisionError(503, "vision_inference_failed", "Inferența locală a eșuat. Verifică memoria și dispozitivul YOLO.") from error
        height, width = frame.shape[:2]
        detections = []
        for result, vocabulary in ((traffic, TRAFFIC_CLASSES),):
            for xyxy, confidence, class_id in zip(result.boxes.xyxy.cpu().tolist(), result.boxes.conf.cpu().tolist(), result.boxes.cls.cpu().tolist()):
                label = vocabulary[int(class_id)]
                if label == "train":
                    label = "rail_vehicle"
                if label == "person" and confidence < .5:
                    continue
                x1, y1, x2, y2 = xyxy
                x1, y1, x2, y2 = max(0., x1), max(0., y1), min(float(width), x2), min(float(height), y2)
                if x2 - x1 < 3 or y2 - y1 < 3:
                    continue
                detections.append({"label": label, "score": round(confidence, 4), "box": [x1, y1, x2 - x1, y2 - y1]})
        traffic_ms = round((time.perf_counter() - started) * 1000)
        candidates = sorted([d for d in detections if d["label"] in {"bus", "rail_vehicle"}], key=lambda d: -d["score"])[:2]
        tram_started = time.perf_counter()
        if candidates:
            try:
                self._classify_trams(image, candidates)
            except Exception as error:
                raise VisionError(503, "vision_tram_failed", "Clasificatorul de tramvaie nu poate fi încărcat. Verifică modelul pregătit local.") from error
        return detections, {
            "name": "YOLO11s + conditional tram classifier", "device": self.device, "input_size": self.imgsz,
            "low_light_enhanced": enhanced, "traffic_ms": traffic_ms,
            "tram_ms": round((time.perf_counter() - tram_started) * 1000), "tram_candidates": len(candidates),
        }

    def _classify_trams(self, image, candidates):
        from ultralytics import YOLOWorld
        from safecross.live_analytics import iou

        if self.model is None:
            model = YOLOWorld(str(model_path()))
            names = model.names
            if (list(names.values()) if isinstance(names, dict) else list(names)) != list(PROMPTS):
                raise ValueError("Unexpected tram vocabulary")
            self.model = model
        height, width = image.shape[:2]
        for detection in candidates:
            x, y, w, h = detection["box"]
            left, top = max(0, int(x - w * .1)), max(0, int(y - h * .1))
            right, bottom = min(width, round(x + w * 1.1)), min(height, round(y + h * 1.1))
            crop = image[top:bottom, left:right]
            result = self.model.predict(crop, imgsz=384, conf=.65, iou=.45, max_det=5, classes=[3], device=self.device, verbose=False)[0]
            for box, confidence in zip(result.boxes.xyxy.cpu().tolist(), result.boxes.conf.cpu().tolist()):
                x1, y1, x2, y2 = box
                if iou(detection["box"], [x1 + left, y1 + top, x2 - x1, y2 - y1]) >= .4:
                    detection["label"] = "tram"
                    detection["score"] = round(min(detection["score"], confidence), 4)
                    detection["classification"] = "open_vocabulary_proposal"
                    break
