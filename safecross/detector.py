"""YOLOX Nano ONNX inference through OpenCV DNN, without torch or cloud calls.

The exported model and its preprocessing contract are documented upstream:
https://github.com/Megvii-BaseDetection/YOLOX/tree/main/demo/ONNXRuntime
This implementation does not download weights, execute model code, or use a GPU.
"""

from dataclasses import dataclass
from hashlib import sha256
import math
from pathlib import Path
from typing import Any


MODEL_URL = "https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_nano.onnx"
MODEL_SOURCE = "https://github.com/Megvii-BaseDetection/YOLOX"
MODEL_INPUT_SIZE = 416
MODEL_SHA256 = "c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d"
COCO_LABELS = {0: "person", 1: "bicycle", 2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}


class SafeCrossError(ValueError):
    """A bounded, operator-actionable analysis failure."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Detection:
    """A current-frame observation; bbox is [left, top, right, bottom] in pixels."""

    bbox: tuple[float, float, float, float]
    confidence: float
    class_id: int

    @property
    def label(self) -> str:
        return COCO_LABELS[self.class_id]

    @property
    def kind(self) -> str:
        return "person" if self.class_id == 0 else "vehicle"


def dependencies():
    """Keep /health and unrelated API routes usable without video dependencies."""
    try:
        import cv2
        import numpy as np
    except ImportError as error:
        raise SafeCrossError(
            "video_dependencies_missing",
            "Instalează requirements-safecross.txt pentru analiza video locală.",
        ) from error
    return cv2, np


def intersection_over_union(first, second) -> float:
    left, top = max(first[0], second[0]), max(first[1], second[1])
    right, bottom = min(first[2], second[2]), min(first[3], second[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    first_area = max(0.0, first[2] - first[0]) * max(0.0, first[3] - first[1])
    second_area = max(0.0, second[2] - second[0]) * max(0.0, second[3] - second[1])
    union = first_area + second_area - intersection
    return intersection / union if union > 0 else 0.0


def suppress_duplicates(detections: list[Detection], threshold: float, limit: int = 80) -> list[Detection]:
    """Class-aware NMS with stable ordering, including ties."""
    ordered = sorted(detections, key=lambda item: (-item.confidence, item.class_id, item.bbox))
    selected: list[Detection] = []
    for candidate in ordered:
        if not any(
            previous.class_id == candidate.class_id
            and intersection_over_union(previous.bbox, candidate.bbox) > threshold
            for previous in selected
        ):
            selected.append(candidate)
            if len(selected) >= limit:
                break
    return selected


class YoloXDetector:
    """Official raw-output YOLOX Nano 416 export, CPU only, COCO classes retained."""

    def __init__(self, model_path: str | Path, confidence_threshold: float = .35, nms_threshold: float = .45):
        cv2, _ = dependencies()
        path = Path(model_path)
        if not path.is_file():
            raise SafeCrossError("model_missing", "Modelul YOLOX Nano ONNX nu este instalat local.")
        if not 1_000_000 <= path.stat().st_size <= 20_000_000:
            raise SafeCrossError("model_invalid", "Dimensiunea modelului nu corespunde exportului YOLOX Nano.")
        model_sha256 = sha256(path.read_bytes()).hexdigest()
        if model_sha256 != MODEL_SHA256:
            raise SafeCrossError("model_checksum_mismatch", "Modelul diferă de exportul oficial YOLOX Nano verificat pentru această versiune.")
        self.confidence_threshold = confidence_threshold
        self.nms_threshold = nms_threshold
        try:
            self.net = cv2.dnn.readNetFromONNX(str(path))
            self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            # OpenCV 5's new graph engine currently ignores target selection and
            # emits a warning for this call; its default OpenCV backend is CPU.
            if int(cv2.__version__.split(".")[0]) < 5:
                self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        except cv2.error as error:
            raise SafeCrossError("model_invalid", "OpenCV nu poate încărca modelul ONNX local.") from error
        self.metadata: dict[str, Any] = {
            "name": "YOLOX-Nano", "format": "ONNX", "input_size": [416, 416],
            "source_url": MODEL_URL, "source_repository": MODEL_SOURCE,
            "release": "0.1.1rc0", "source_license": "Apache-2.0",
            "sha256": model_sha256,
            "runtime": "OpenCV DNN CPU", "runtime_version": cv2.__version__,
            "weights_dataset": "COCO", "output_decode": "raw-strides-8-16-32",
            "preprocessing": "BGR float32 0..255; top-left letterbox; padding 114",
            "classes": {str(key): value for key, value in COCO_LABELS.items()},
            "max_detections_per_frame": 80,
        }

    def detect(self, frame) -> list[Detection]:
        cv2, np = dependencies()
        height, width = frame.shape[:2]
        scale = min(MODEL_INPUT_SIZE / height, MODEL_INPUT_SIZE / width)
        resized = cv2.resize(frame, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_LINEAR)
        padded = np.full((MODEL_INPUT_SIZE, MODEL_INPUT_SIZE, 3), 114, dtype=np.uint8)
        padded[:resized.shape[0], :resized.shape[1]] = resized
        blob = cv2.dnn.blobFromImage(padded, scalefactor=1.0, swapRB=False, crop=False)
        try:
            self.net.setInput(blob)
            raw = self.net.forward()
        except cv2.error as error:
            raise SafeCrossError("inference_failed", "Inferența ONNX a eșuat; verifică modelul și runtime-ul.") from error
        return self.decode(raw, scale, width, height)

    def decode(self, raw, scale: float, width: int, height: int) -> list[Detection]:
        """Decode the upstream release's raw predictions; never guess another export layout."""
        _, np = dependencies()
        predictions = np.asarray(raw)
        expected_rows = sum((MODEL_INPUT_SIZE // stride) ** 2 for stride in (8, 16, 32))
        if predictions.shape != (1, expected_rows, 85) or not np.isfinite(predictions).all():
            raise SafeCrossError("model_output_invalid", "Modelul trebuie să producă exportul brut YOLOX Nano [1,3549,85].")
        predictions = predictions[0].copy()
        offset = 0
        for stride in (8, 16, 32):
            side = MODEL_INPUT_SIZE // stride
            count = side * side
            yy, xx = np.mgrid[:side, :side]
            grid = np.stack((xx, yy), axis=-1).reshape(-1, 2)
            section = predictions[offset:offset + count]
            section[:, :2] = (section[:, :2] + grid) * stride
            section[:, 2:4] = np.exp(np.clip(section[:, 2:4], -20, 20)) * stride
            offset += count
        class_ids = predictions[:, 5:].argmax(axis=1)
        confidences = predictions[:, 4] * predictions[np.arange(expected_rows), class_ids + 5]
        keep = np.isin(class_ids, list(COCO_LABELS)) & (confidences >= self.confidence_threshold)
        detections: list[Detection] = []
        for row_index in np.flatnonzero(keep):
            center_x, center_y, box_width, box_height = predictions[row_index, :4] / scale
            bbox = (
                max(0.0, float(center_x - box_width / 2)), max(0.0, float(center_y - box_height / 2)),
                min(float(width), float(center_x + box_width / 2)), min(float(height), float(center_y + box_height / 2)),
            )
            confidence = float(confidences[row_index])
            if bbox[2] - bbox[0] >= 2 and bbox[3] - bbox[1] >= 2 and math.isfinite(confidence) and 0 <= confidence <= 1:
                detections.append(Detection(bbox, confidence, int(class_ids[row_index])))
        return suppress_duplicates(detections, self.nms_threshold)
