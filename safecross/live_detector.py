"""Offline YOLO-World inference; vocabulary is embedded by live_setup, once."""

import importlib.util
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "runtime/models/traffic-world.pt"
TRAFFIC_MODEL_PATH = ROOT / "runtime/models/yolo11s.pt"
TRAFFIC_CLASSES = {0: "person", 1: "bicycle", 2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
LABELS = ("person", "car", "bus", "tram", "truck", "motorcycle", "bicycle")
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
            from ultralytics import YOLO, YOLOWorld
            from ultralytics import settings

            settings.update({"sync": False, "weights_dir": str(ROOT / "runtime/models"), "runs_dir": str(ROOT / "runtime/runs")})
            torch.set_num_threads(min(4, os.cpu_count() or 1))
            self.model = YOLOWorld(str(model_path()))
            self.traffic = YOLO(str(traffic_model_path()))
            if any(self.traffic.names.get(key) != value for key, value in TRAFFIC_CLASSES.items()):
                raise ValueError("Unexpected traffic classes")
            names = self.model.names
            actual = list(names.values()) if isinstance(names, dict) else list(names)
            if actual != list(PROMPTS):
                raise ValueError("Unexpected vocabulary")
            self.device = os.environ.get("SAFEIASI_VISION_DEVICE", "0" if torch.cuda.is_available() else "cpu")
            self.imgsz = int(os.environ.get("SAFEIASI_VISION_IMGSZ", "1280"))
            if self.imgsz not in (640, 960, 1280):
                raise ValueError("SAFEIASI_VISION_IMGSZ must be 640, 960 or 1280")
        except Exception as error:
            raise VisionError(503, "vision_model_invalid", "Modelul local nu poate fi încărcat. Rulează python -m safecross.live_setup; verifică dispozitivul configurat.") from error

    def detect(self, frame):
        import cv2
        import numpy as np

        # Improve local contrast for detection only. Lighting always uses the original.
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        enhanced = float(np.median(gray)) < 65
        image = frame
        if enhanced:
            lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
            lab[:, :, 0] = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(lab[:, :, 0])
            image = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        try:
            traffic = self.traffic.predict(
                image, imgsz=self.imgsz, conf=.35, iou=.45, max_det=150,
                classes=list(TRAFFIC_CLASSES), device=self.device, verbose=False,
            )[0]
            trams = self.model.predict(
                image, imgsz=min(960, self.imgsz), conf=.5, iou=.45, max_det=20,
                classes=[3], device=self.device, verbose=False,
            )[0]
        except Exception as error:
            raise VisionError(503, "vision_inference_failed", "Inferența locală a eșuat. Verifică memoria și dispozitivul YOLO.") from error
        height, width = frame.shape[:2]
        detections = []
        for result, vocabulary in ((traffic, TRAFFIC_CLASSES), (trams, {3: "tram"})):
            for xyxy, confidence, class_id in zip(result.boxes.xyxy.cpu().tolist(), result.boxes.conf.cpu().tolist(), result.boxes.cls.cpu().tolist()):
                label = vocabulary[int(class_id)]
                if label == "person" and confidence < .5:
                    continue
                x1, y1, x2, y2 = xyxy
                x1, y1, x2, y2 = max(0., x1), max(0., y1), min(float(width), x2), min(float(height), y2)
                if x2 - x1 < 3 or y2 - y1 < 3:
                    continue
                detections.append({"label": label, "score": round(confidence, 4), "box": [x1, y1, x2 - x1, y2 - y1]})
        from safecross.live_analytics import iou

        # A confidently proposed tram replaces an overlapping generic bus/truck box.
        tram_boxes = [d["box"] for d in detections if d["label"] == "tram"]
        detections = [d for d in detections if d["label"] not in {"bus", "truck", "car"} or not any(iou(d["box"], box) > .5 for box in tram_boxes)]
        return detections, {"name": "YOLO11s + YOLO-World trams", "device": self.device, "input_size": self.imgsz, "low_light_enhanced": enhanced}
