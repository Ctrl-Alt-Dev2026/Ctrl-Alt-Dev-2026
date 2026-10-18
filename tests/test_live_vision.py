"""Live transport and temporal/lighting behavior. Synthetic fixtures are not accuracy evidence."""

import copy
import importlib.util
import struct
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

from fastapi.testclient import TestClient

from api.main import create_app
from safecross.live import LiveVision, MAX_FRAME_BYTES, MAX_SESSIONS, SessionConfig, jpeg_dimensions
from safecross.live_analytics import Analytics
from safecross.live_detector import VisionError
from safecross.live_detector import LiveDetector


VIDEO_READY = all(importlib.util.find_spec(name) for name in ("cv2", "numpy"))
REGION = {"id": "crossing", "polygon": [[.1, .1], [.5, .1], [.5, .5], [.1, .5]]}


class FakeDetector:
    def detect(self, frame):
        return [{"label": "bus", "score": .9, "box": [20., 20., 80., 50.]}], {"name": "synthetic-test-detector", "low_light_enhanced": False}


@unittest.skipUnless(VIDEO_READY, "Optional OpenCV/NumPy are not installed")
class LiveApiTests(unittest.TestCase):
    def setUp(self):
        import cv2
        import numpy as np

        self.app = create_app()
        self.app.state.live_vision = LiveVision(FakeDetector)
        self.client = TestClient(self.app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000))
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.ready = patch("api.vision_router.readiness", return_value={"available": True})
        self.ready.start()
        self.addCleanup(self.ready.stop)
        self.jpeg = cv2.imencode(".jpg", np.full((120, 160, 3), 100, dtype=np.uint8))[1].tobytes()

    def open(self, **changes):
        response = self.client.post("/api/v1/vision/sessions", json={"camera_id": "test-camera", "crosswalks": [REGION]} | changes)
        self.assertEqual(201, response.status_code, response.text)
        return response.json()["session_id"]

    def frame(self, session, seq=0, time=1, **changes):
        return self.client.post(f"/api/v1/vision/sessions/{session}/frames?sequence={seq}&media_time={time}", content=changes.get("data", self.jpeg), headers={"content-type": changes.get("content_type", "image/jpeg")})

    def test_frames_echo_identity_and_source_dimensions_and_track_objects(self):
        key = self.open()
        first = self.frame(key).json()
        second = self.frame(key, 1, 1.5).json()
        self.assertEqual((160, 120, 0, 1), (first["width"], first["height"], first["sequence"], first["media_time"]))
        self.assertEqual(first["detections"][0]["track_id"], second["detections"][0]["track_id"])
        self.assertEqual("unverified_signals_only", first["incident_status"])
        self.assertEqual([], first["signals"])
        self.assertEqual(1, len(first["light"]["crosswalks"]))

    def test_out_of_order_sequence_and_time_are_rejected(self):
        key = self.open()
        self.assertEqual(200, self.frame(key, 2, 5).status_code)
        for sequence, timestamp in ((2, 6), (1, 6), (3, 4), (3, 5)):
            self.assertEqual(409, self.frame(key, sequence, timestamp).status_code)

    def test_delete_and_expiration_reject_late_results(self):
        key = self.open()
        self.assertEqual(204, self.client.delete(f"/api/v1/vision/sessions/{key}").status_code)
        self.assertEqual(404, self.frame(key).status_code)
        key = self.open()
        self.app.state.live_vision.sessions[key].touched -= 121
        self.assertEqual(404, self.frame(key).status_code)

    def test_bounded_bytes_type_and_jpeg_validation(self):
        key = self.open()
        for data, content_type, status in ((b"invalid", "image/jpeg", 422), (self.jpeg, "image/png", 415), (b"x" * (MAX_FRAME_BYTES + 1), "image/jpeg", 413)):
            self.assertEqual(status, self.frame(key, data=data, content_type=content_type).status_code)

    def test_compressed_large_dimensions_rejected_before_decode(self):
        fake_jpeg = b"\xff\xd8\xff\xc0" + struct.pack(">HBHH", 8, 8, 9000, 9000) + b"\x00"
        with patch("cv2.imdecode", side_effect=AssertionError("must not decode")):
            self.assertEqual(413, self.frame(self.open(), data=fake_jpeg).status_code)

    def test_no_model_or_network_on_health_or_status(self):
        with patch("safecross.live.LiveDetector", side_effect=AssertionError("must remain lazy")):
            self.assertEqual(200, self.client.get("/health").status_code)
            self.assertEqual(200, self.client.get("/api/v1/vision/status").status_code)

    def test_missing_model_is_actionable(self):
        with patch("api.vision_router.readiness", return_value={"available": False, "message": "install detector"}):
            response = self.client.post("/api/v1/vision/sessions", json={"camera_id": "test"})
        self.assertEqual(503, response.status_code)
        self.assertEqual("vision_not_ready", response.json()["detail"]["code"])

    def test_bad_polygons_are_rejected(self):
        for polygon in ([[[0, 0], [1, 0]]], [[[0, 0], [1, 0], [2, 1]]], [[[0, 0], [.5, .5], [1, 1]]]):
            response = self.client.post("/api/v1/vision/sessions", json={"camera_id": "test", "crosswalks": [{"id": "r", "polygon": polygon[0]}]})
            self.assertEqual(422, response.status_code)

    def test_session_limit_and_busy_inference_have_no_queue(self):
        for _ in range(MAX_SESSIONS):
            key = self.open()
        self.assertEqual(429, self.client.post("/api/v1/vision/sessions", json={"camera_id": "extra"}).status_code)
        lock = self.app.state.live_vision.inference_lock
        lock.acquire()
        try:
            self.assertEqual(429, self.frame(key).status_code)
        finally:
            lock.release()

    def test_cross_origin_and_remote_access_denied(self):
        self.assertEqual(403, self.client.get("/api/v1/vision/status", headers={"Origin": "https://untrusted.example"}).status_code)
        with TestClient(self.app, base_url="http://127.0.0.1", client=("192.0.2.5", 50000)) as remote:
            self.assertEqual(403, remote.get("/api/v1/vision/status").status_code)

    def test_detection_region_crops_inference_and_restores_frame_coordinates(self):
        seen = []
        def focused(frame):
            seen.append(frame.shape[:2])
            return [{"label": "car", "score": .9, "box": [8., 8., 16., 16.]}], {"name": "synthetic-region-test"}
        self.app.state.live_vision.detector = SimpleNamespace(detect=focused)
        response = self.frame(self.open(detection_region=REGION))
        self.assertEqual(200, response.status_code, response.text)
        result = response.json()
        self.assertEqual([(49, 65)], seen)
        self.assertEqual([24., 20., 16., 16.], result["detections"][0]["box"])
        self.assertEqual((160, 120), (result["width"], result["height"]))

    def test_detection_region_excludes_observations_outside_polygon(self):
        region = {"id": "triangle", "polygon": [[0, 0], [.8, 0], [0, .8]]}
        self.app.state.live_vision.detector = SimpleNamespace(detect=lambda frame: (
            [{"label": "car", "score": .9, "box": [100., 65., 20., 20.]}], {"name": "synthetic-region-test"}))
        result = self.frame(self.open(detection_region=region))
        self.assertEqual(200, result.status_code)
        self.assertEqual([], result.json()["detections"])

    def test_small_detection_region_returns_actionable_error(self):
        region = {"id": "tiny", "polygon": [[0, 0], [.1, 0], [.1, .1], [0, .1]]}
        result = self.frame(self.open(detection_region=region))
        self.assertEqual(422, result.status_code)
        self.assertEqual("detection_region_small", result.json()["detail"]["code"])


@unittest.skipUnless(VIDEO_READY, "Optional OpenCV/NumPy are not installed")
class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        import numpy as np
        self.np = np
        self.frame = np.full((200, 400, 3), 150, dtype=np.uint8)
        self.analytics = Analytics()

    def update(self, detections=(), timestamp=0, crosswalks=()):
        return self.analytics.update(copy.deepcopy(list(detections)), self.frame, timestamp, list(crosswalks))

    def test_dark_sky_does_not_flag_bright_crosswalk(self):
        self.frame[:20] = 0
        result = self.update(crosswalks=[REGION])
        self.assertFalse(result[1]["crosswalks"][0]["low_light"])
        self.assertEqual([], result[2])

    def test_crosswalk_low_light_requires_persistence_and_has_cooldown(self):
        self.frame[20:101, 40:201] = 10
        self.assertEqual([], self.update(timestamp=0, crosswalks=[REGION])[2])
        self.assertEqual([], self.update(timestamp=1, crosswalks=[REGION])[2])
        result = self.update(timestamp=2, crosswalks=[REGION])
        self.assertEqual("iluminat", result[2][0]["kind"])
        self.assertEqual([], self.update(timestamp=3, crosswalks=[REGION])[2])

    def test_dark_image_without_crosswalk_never_claims_crosswalk_light(self):
        self.frame[:] = 0
        for timestamp in range(5):
            result = self.update(timestamp=timestamp)
            self.assertEqual([], result[1]["crosswalks"])
            self.assertEqual([], result[2])

    def test_parked_and_overlapping_objects_do_not_create_accidents(self):
        detections = [{"label": "car", "box": [20, 30, 80, 40], "score": .9}, {"label": "person", "box": [40, 30, 20, 40], "score": .8}]
        for timestamp in range(100):
            self.assertEqual([], self.update(detections, timestamp)[2])

    def test_motion_then_stop_and_persistent_overlap_produces_review_signal(self):
        signals = []
        # Synthetic image-coordinate motion, not a real collision fixture.
        for index, x in enumerate([10, 25, 40, 55, 55, 55, 55, 55, 55, 55]):
            detections = [{"label": "car", "box": [x, 30, 60, 40], "score": .9}, {"label": "person", "box": [80, 30, 20, 40], "score": .8}]
            signals.extend(self.update(detections, index * .5)[2])
        self.assertEqual(1, len(signals))
        self.assertEqual("incident", signals[0]["kind"])
        self.assertEqual("needs_review", signals[0]["status"])

    def test_long_frame_gap_resets_motion_and_contact_evidence(self):
        detection = [{"label": "tram", "box": [20, 30, 80, 40], "score": .9}]
        first = self.update(detection, 0)
        second = self.update(detection, 10)
        self.assertTrue(second[3])
        self.assertNotEqual(first[0][0]["track_id"], second[0][0]["track_id"])

    def test_one_track_cannot_match_two_detections(self):
        detection = {"label": "car", "box": [20, 30, 80, 40], "score": .9}
        self.update([detection], 0)
        result = self.update([detection, dict(detection)], .5)
        self.assertEqual(2, len({d["track_id"] for d in result[0]}))

    def test_weak_detections_need_two_observations_before_display(self):
        detection = {"label": "car", "box": [20, 30, 80, 40], "score": .45}
        self.assertEqual([], self.update([detection], 0)[0])
        self.assertEqual(1, len(self.update([detection], .25)[0]))
        self.assertEqual([], self.update([detection], 5)[0])

    def test_high_confidence_detections_appear_immediately(self):
        detection = {"label": "person", "box": [20, 30, 20, 40], "score": .9}
        self.assertEqual(1, len(self.update([detection], 0)[0]))


@unittest.skipUnless(VIDEO_READY and importlib.util.find_spec("torch"), "Optional detector dependencies are not installed")
class ConditionalDetectorTests(unittest.TestCase):
    def make_detector(self, class_ids):
        tensor = lambda value: SimpleNamespace(cpu=lambda: SimpleNamespace(tolist=lambda: value))
        boxes = SimpleNamespace(
            xyxy=tensor([[20., 20., 80., 80.] for _ in class_ids]),
            conf=tensor([.9] * len(class_ids)), cls=tensor(class_ids),
        )
        detector = object.__new__(LiveDetector)
        detector.traffic = SimpleNamespace(predict=Mock(return_value=[SimpleNamespace(boxes=boxes)]))
        detector.device, detector.imgsz = "cpu", 960
        detector._classify_trams = Mock()
        return detector

    def test_car_only_frames_skip_secondary_model(self):
        import numpy as np
        detector = self.make_detector([2])
        detections, metadata = detector.detect(np.full((120, 160, 3), 150, dtype=np.uint8))
        detector._classify_trams.assert_not_called()
        self.assertEqual("car", detections[0]["label"])
        self.assertEqual(0, metadata["tram_candidates"])

    def test_bus_and_rail_candidates_are_bounded_and_never_called_trams_implicitly(self):
        import numpy as np
        detector = self.make_detector([5, 6, 5])
        detections, metadata = detector.detect(np.full((120, 160, 3), 150, dtype=np.uint8))
        detector._classify_trams.assert_called_once()
        self.assertEqual(2, metadata["tram_candidates"])
        self.assertEqual(["bus", "rail_vehicle", "bus"], [d["label"] for d in detections])


if __name__ == "__main__":
    unittest.main()
