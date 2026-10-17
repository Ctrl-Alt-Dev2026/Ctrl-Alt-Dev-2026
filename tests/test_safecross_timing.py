"""Timing checks on mocked decoded PTS, without inference or external media."""

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from safecross.detector import SafeCrossError
from safecross.timing import verify_video_timing


class TimingPreflightTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.source = Path(temporary.name) / "synthetic-input.mp4"
        self.source.write_bytes(b"Explicit mock input; no actual video decoded by these unit tests.")
        self.metadata = {"streams": [{"width": 1280, "height": 720, "avg_frame_rate": "30/1", "r_frame_rate": "30/1", "time_base": "1/15360", "start_time": "0.000000", "duration": "1.000000", "nb_frames": "30"}]}
        self.frames = {"frames": [{"best_effort_timestamp_time": f"{index / 30:.6f}"} for index in range(30)]}

    def verify(self, metadata=None, frames=None):
        with patch("safecross.timing.shutil.which", return_value="ffprobe"), patch("safecross.timing._probe_json", side_effect=[metadata or self.metadata, frames or self.frames]) as probe:
            result = verify_video_timing(self.source)
            self.assertIn("-read_intervals", probe.call_args_list[1].args[0])
            self.assertIn("%+121", probe.call_args_list[1].args[0])
            self.assertLessEqual(probe.call_args_list[1].args[1], 20)
            self.assertEqual(2 * 1024 * 1024, probe.call_args_list[1].args[2])
            return result

    def test_all_cfr_pts_are_verified_and_provenance_retains_tolerance(self):
        result = self.verify()
        self.assertEqual("ffprobe_cfr_verified", result["validation"])
        self.assertEqual(30, result["frame_count"])
        self.assertEqual(30, result["fps"])
        self.assertLess(result["max_error_s"], .000001)
        self.assertEqual(.001, result["tolerance_s"])

    def test_average_rate_equality_and_monotonic_pts_do_not_admit_variable_fps(self):
        frames = deepcopy(self.frames)
        for index in range(10, 20):
            frames["frames"][index]["best_effort_timestamp_time"] = str(index / 30 + .015)
        with self.assertRaises(SafeCrossError) as caught:
            self.verify(frames=frames)
        self.assertEqual("video_variable_fps", caught.exception.code)

    def test_missing_tool_never_silently_accepts_the_source(self):
        with patch("safecross.timing.shutil.which", return_value=None), self.assertRaises(SafeCrossError) as caught:
            verify_video_timing(self.source)
        self.assertEqual("ffprobe_missing", caught.exception.code)

    def test_missing_or_duplicate_pts_are_rejected(self):
        for invalid in ({}, {"best_effort_timestamp_time": "nan"}, {"best_effort_timestamp_time": "0.000000"}):
            frames = deepcopy(self.frames)
            frames["frames"][1] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(SafeCrossError) as caught:
                self.verify(frames=frames)
            self.assertEqual("video_timing_invalid", caught.exception.code)

    def test_nonzero_time_origin_is_rejected_instead_of_shifting_the_overlay_silently(self):
        frames = deepcopy(self.frames)
        for frame in frames["frames"]:
            frame["best_effort_timestamp_time"] = str(float(frame["best_effort_timestamp_time"]) + .1)
        with self.assertRaises(SafeCrossError) as caught:
            self.verify(frames=frames)
        self.assertEqual("video_time_origin_unsupported", caught.exception.code)

    def test_metadata_bounds_fail_before_per_frame_probe(self):
        for field, value, code in (("width", 4097, "video_dimensions_unsupported"), ("height", 2160, "video_dimensions_unsupported"), ("avg_frame_rate", "121/1", "video_fps_unsupported"), ("duration", "121", "video_duration_unsupported"), ("avg_frame_rate", "0/0", "video_timing_invalid")):
            metadata = deepcopy(self.metadata)
            metadata["streams"][0][field] = value
            with self.subTest(field=field), patch("safecross.timing.shutil.which", return_value="ffprobe"), patch("safecross.timing._probe_json", return_value=metadata) as probe, self.assertRaises(SafeCrossError) as caught:
                verify_video_timing(self.source)
            self.assertEqual(code, caught.exception.code)
            self.assertEqual(1, probe.call_count)

    def test_declared_frame_count_and_duration_mismatches_are_rejected(self):
        for field, value, code in (("nb_frames", "31", "video_timing_frame_count_mismatch"), ("duration", "1.5", "video_timing_duration_mismatch")):
            metadata = deepcopy(self.metadata)
            metadata["streams"][0][field] = value
            with self.subTest(field=field), self.assertRaises(SafeCrossError) as caught:
                self.verify(metadata=metadata)
            self.assertEqual(code, caught.exception.code)

    def test_coarse_timestamp_resolution_cannot_expand_the_cfr_tolerance_arbitrarily(self):
        for time_base in ("1/1", "1/30"):
            metadata = deepcopy(self.metadata)
            metadata["streams"][0]["time_base"] = time_base
            with self.subTest(time_base=time_base), patch("safecross.timing.shutil.which", return_value="ffprobe"), patch("safecross.timing._probe_json", return_value=metadata) as probe, self.assertRaises(SafeCrossError) as caught:
                verify_video_timing(self.source)
            self.assertEqual("video_timing_resolution_unsupported", caught.exception.code)
            self.assertEqual(1, probe.call_count)

    def test_webm_format_duration_is_used_only_when_stream_duration_is_unavailable(self):
        metadata = deepcopy(self.metadata)
        del metadata["streams"][0]["duration"]
        metadata["format"] = {"duration": "1.000000"}
        result = self.verify(metadata=metadata)
        self.assertEqual(1, result["declared_duration_s"])

    def test_upload_byte_limit_prevents_probe_of_oversized_sources(self):
        with patch("safecross.timing.MAX_UPLOAD_BYTES", 1), patch("safecross.timing._probe_json") as probe, self.assertRaises(SafeCrossError) as caught:
            verify_video_timing(self.source)
        self.assertEqual("video_too_large", caught.exception.code)
        probe.assert_not_called()


if __name__ == "__main__":
    unittest.main()
