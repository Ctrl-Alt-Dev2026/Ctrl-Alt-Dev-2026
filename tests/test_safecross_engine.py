"""Synthetic mechanical checks; no claim of model accuracy on real traffic."""

from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from safecross.detector import Detection, SafeCrossError, YoloXDetector, dependencies, suppress_duplicates
from safecross.engine import CandidateCollector, SimpleTracker, analyze_video, image_gap, in_roi, validate_config


class GeometryAndTrackingTests(unittest.TestCase):
    def config(self, **extra):
        return validate_config({"fixed_camera_confirmed": True, **extra})

    def test_config_requires_explicit_fixed_camera_and_rejects_nonfinite_limits(self):
        for config in ({}, {"fixed_camera_confirmed": 1}, {"fixed_camera_confirmed": True, "sample_fps": float("nan")}, {"fixed_camera_confirmed": True, "sample_fps": True}, {"fixed_camera_confirmed": True, "max_frames": 601}):
            with self.subTest(config=config), self.assertRaises(SafeCrossError):
                validate_config(config)

    def test_roi_uses_normalized_bottom_center_and_rejects_zero_area(self):
        roi = [[.1, .1], [.5, .1], [.5, .8], [.1, .8]]
        self.assertTrue(in_roi((20, 10, 40, 70), roi, 100, 100))
        self.assertFalse(in_roi((70, 10, 90, 70), roi, 100, 100))
        with self.assertRaises(SafeCrossError):
            self.config(roi=[[0, 0], [.5, .5], [1, 1]])

    def test_bbox_gap_is_image_fraction_and_not_center_or_ground_distance(self):
        self.assertEqual(0, image_gap((0, 0, 20, 20), (10, 5, 30, 15), 100, 100))
        self.assertAlmostEqual(10 / (20000 ** .5), image_gap((0, 0, 20, 20), (30, 5, 40, 15), 100, 100))

    def test_nms_is_class_aware_and_deterministic(self):
        first = Detection((10, 10, 30, 50), .9, 0)
        duplicate = Detection((11, 10, 31, 50), .8, 0)
        car = Detection((10, 10, 30, 50), .7, 2)
        self.assertEqual([first, car], suppress_duplicates([duplicate, car, first], .45))

    def test_tracker_keeps_ids_across_small_motion_but_never_interpolates_missing_frame(self):
        tracker = SimpleTracker(320, 240)
        first = tracker.update([Detection((10, 20, 30, 90), .8, 0)], 0, 0, 0)
        self.assertEqual([], tracker.update([], .2, 4, 1))
        again = tracker.update([Detection((12, 20, 32, 90), .8, 0)], .4, 8, 2)
        self.assertEqual(first[0]["track_id"], again[0]["track_id"])
        self.assertEqual(1, tracker.summary()[0]["gap_count"])
        after_gap = tracker.update([Detection((12, 20, 32, 90), .8, 0)], 1.4, 28, 7)
        self.assertNotEqual(again[0]["track_id"], after_gap[0]["track_id"])

    def test_tracker_does_not_relabel_person_as_vehicle(self):
        tracker = SimpleTracker(320, 240)
        person = tracker.update([Detection((10, 20, 30, 90), .8, 0)], 0, 0, 0)
        vehicle = tracker.update([Detection((10, 20, 30, 90), .8, 2)], .2, 4, 1)
        self.assertNotEqual(person[0]["track_id"], vehicle[0]["track_id"])

    def objects(self, x):
        return [
            {"track_id": "person-1", "kind": "person", "label": "person", "bbox": [100, 80, 125, 170], "confidence": .9},
            {"track_id": "car-1", "kind": "vehicle", "label": "car", "bbox": [x, 120, x + 60, 175], "confidence": .9},
        ]

    def test_collector_requires_persistence_motion_and_retains_same_frame_evidence(self):
        collector = CandidateCollector(320, 240, self.config())
        for index, x in enumerate((120, 124, 128, 132, 136)):
            collector.update(self.objects(x), index * .2, index * 4, index)
        result = collector.finish()
        self.assertEqual(1, len(result))
        candidate = result[0]
        self.assertEqual(5, candidate["proximity_observation_count"])
        self.assertEqual("pending", candidate["review_status"])
        self.assertFalse(candidate["confirmed_conflict"])
        self.assertEqual(candidate["representative_s"], candidate["evidence"]["time_s"])
        self.assertEqual("person-1", candidate["evidence"]["person"]["track_id"])
        self.assertGreater(candidate["vehicle_image_displacement_normalized"], .01)

    def test_collector_suppresses_single_frame_and_stationary_vehicle(self):
        collector = CandidateCollector(320, 240, self.config())
        collector.update(self.objects(120), 0, 0, 0)
        self.assertEqual([], collector.finish())
        self.assertEqual(1, collector.discarded_isolated)
        parked = CandidateCollector(320, 240, self.config())
        for index in range(6):
            parked.update(self.objects(120 + index % 2), index * .2, index * 4, index)
        self.assertEqual([], parked.finish())
        self.assertEqual(1, parked.discarded_stationary)

    def test_collector_never_joins_nonconsecutive_single_frame_hits(self):
        collector = CandidateCollector(320, 240, self.config())
        for index in range(9):
            collector.update(self.objects(120 + index) if index % 2 == 0 else [], index * .2, index * 4, index)
        self.assertEqual([], collector.finish())

    def test_collector_respects_roi_without_claiming_crosswalk_is_present(self):
        collector = CandidateCollector(320, 240, self.config(roi=[[0, 0], [.2, 0], [.2, 1], [0, 1]]))
        for index in range(5):
            collector.update(self.objects(120 + index * 4), index * .2, index * 4, index)
        self.assertEqual([], collector.finish())

    def two_wheeler_objects(self, index, mode="rider", label="bicycle"):
        x = 100 + index * 8
        person_x = x + 25 if mode == "rider" else 125
        person_y = 65 - index * 5 if mode == "crossing" else 65
        return [
            {"track_id": "person-1", "kind": "person", "label": "person", "bbox": [person_x, person_y, person_x + 20, person_y + 105], "confidence": .9},
            {"track_id": "bike-1", "kind": "vehicle", "label": label, "bbox": [x, 120, x + 80, 175], "confidence": .9},
        ]

    def test_two_wheeler_with_own_rider_is_suppressed_after_supported_coupled_observations(self):
        for label in ("bicycle", "motorcycle"):
            with self.subTest(label=label):
                collector = CandidateCollector(320, 240, self.config())
                for index in range(5):
                    collector.update(self.two_wheeler_objects(index, label=label), index * .2, index * 4, index)
                self.assertEqual([], collector.finish())
                self.assertEqual(1, collector.discarded_possible_rider)

    def test_distinct_pedestrian_is_not_suppressed_as_rider_of_passing_bicycle(self):
        for mode in ("standing", "crossing"):
            with self.subTest(mode=mode):
                collector = CandidateCollector(320, 240, self.config())
                for index in range(5):
                    collector.update(self.two_wheeler_objects(index, mode=mode), index * .2, index * 4, index)
                self.assertEqual(1, len(collector.finish()))
                self.assertEqual(0, collector.discarded_possible_rider)


class SyntheticVideoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.cv2, cls.np = dependencies()
        except SafeCrossError as error:
            raise unittest.SkipTest(error.message)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.source = self.directory / "explicitly-synthetic.avi"
        writer = self.cv2.VideoWriter(str(self.source), self.cv2.VideoWriter_fourcc(*"MJPG"), 20, (320, 240))
        self.assertTrue(writer.isOpened())
        for index in range(40):
            frame = self.np.full((240, 320, 3), 40, dtype=self.np.uint8)
            self.cv2.putText(frame, f"SYNTHETIC {index}", (10, 25), self.cv2.FONT_HERSHEY_SIMPLEX, .5, (220, 220, 220), 1)
            writer.write(frame)
        writer.release()

    class SyntheticDetector:
        metadata = {"name": "explicit-synthetic-test-double", "synthetic": True}

        def __init__(self):
            self.index = 0

        def detect(self, frame):
            offset = self.index * 3
            self.index += 1
            return [Detection((100, 80, 125, 170), .9, 0), Detection((120 + offset, 120, 180 + offset, 175), .9, 2)]

    def test_video_pipeline_creates_auditable_samples_artifacts_and_pending_candidates(self):
        progress = []
        output = self.directory / "job"
        result = analyze_video(self.source, output, {"fixed_camera_confirmed": True}, progress.append, self.SyntheticDetector())
        self.assertEqual(10, result["sampled_frame_count"])
        self.assertEqual(2, result["video"]["duration_s"])
        self.assertEqual((320, 240), (result["video"]["width"], result["video"]["height"]))
        self.assertEqual([index * 4 for index in range(10)], [frame["frame_index"] for frame in result["frames"]])
        self.assertEqual(1, result["candidate_count"])
        self.assertEqual("uncalibrated", result["calibration"])
        self.assertEqual(sha256(self.source.read_bytes()).hexdigest(), result["source_sha256"])
        self.assertEqual("local_video_analysis", result["response_origin"])
        self.assertEqual("complete", progress[-1]["stage"])
        for name in ("poster.jpg", "annotated.avi", result["candidates"][0]["snapshot"]):
            self.assertGreater((output / name).stat().st_size, 0)
        json.dumps(result, allow_nan=False)
        self.assertNotIn("model_path", result["parameters"])

    def test_declared_duration_is_rejected_before_partial_artifacts_are_published(self):
        output = self.directory / "too-long"
        with self.assertRaises(SafeCrossError) as caught:
            analyze_video(self.source, output, {"fixed_camera_confirmed": True, "max_duration_seconds": 1}, detector=self.SyntheticDetector())
        self.assertEqual("video_too_long", caught.exception.code)
        self.assertEqual([], list(output.iterdir()))

    def test_sampling_limit_rejects_instead_of_silently_truncating(self):
        with self.assertRaises(SafeCrossError) as caught:
            analyze_video(self.source, self.directory / "too-many", {"fixed_camera_confirmed": True, "max_frames": 3}, detector=self.SyntheticDetector())
        self.assertEqual("too_many_frames", caught.exception.code)

    def test_partial_artifacts_are_cleaned_when_detector_fails(self):
        class FailingDetector(self.SyntheticDetector):
            def detect(self, frame):
                if self.index > 1:
                    raise SafeCrossError("test_failure", "Explicit test failure")
                return super().detect(frame)
        output = self.directory / "failing"
        with self.assertRaises(SafeCrossError):
            analyze_video(self.source, output, {"fixed_camera_confirmed": True}, detector=FailingDetector())
        self.assertEqual([], list(output.iterdir()))

    def test_missing_or_invalid_model_does_not_fall_back_to_fake_detections(self):
        with self.assertRaises(SafeCrossError) as caught:
            analyze_video(self.source, self.directory / "no-model", {"fixed_camera_confirmed": True, "model_path": self.directory / "missing.onnx"})
        self.assertEqual("model_missing", caught.exception.code)

    def test_raw_yolox_decode_retains_class_ids_and_rescales_to_source_pixels(self):
        detector = object.__new__(YoloXDetector)
        detector.confidence_threshold, detector.nms_threshold = .35, .45
        raw = self.np.zeros((1, 3549, 85), dtype=self.np.float32)
        row = 10 * 52 + 10
        raw[0, row, :4] = [1.25, 1.25, self.np.log(20 / 8), self.np.log(40 / 8)]
        raw[0, row, 4], raw[0, row, 5] = .9, .9
        detections = detector.decode(raw, 2, 320, 240)
        self.assertEqual(1, len(detections))
        self.assertEqual(0, detections[0].class_id)
        self.assertAlmostEqual(.81, detections[0].confidence, places=5)
        self.assertEqual((40, 35, 50, 55), tuple(round(value) for value in detections[0].bbox))
        with self.assertRaises(SafeCrossError):
            detector.decode(self.np.zeros((1, 1, 85)), 2, 320, 240)


if __name__ == "__main__":
    unittest.main()
