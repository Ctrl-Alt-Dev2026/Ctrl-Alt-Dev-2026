"""HTTP boundaries and persisted video review with an injected runner, no AI download.

The fake runner deliberately exercises API orchestration only. Detection quality and
actual video decoding are covered separately; these fixtures are synthetic bytes.
"""

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import json
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import create_app
from safecross.detector import SafeCrossError
from safecross.jobs import LIMITS


API = "/api/v1/safecross"
SOURCE = b"synthetic API upload, not a real video or inference result"
READY = {
    "available": True, "model_ready": True, "dependencies_ready": True,
    "model": {"name": "test-injected-runner", "sha256": "test-only"},
    "limits": LIMITS, "message": "Synthetic test runner only.",
}
RESULT = {
    "video": {"width": 640, "height": 360, "fps": 25, "duration_s": 2},
    "frames": [{"time_s": 1, "objects": [
        {"track_id": "person-1", "label": "person", "confidence": .8, "bbox": [100, 100, 130, 180]},
        {"track_id": "vehicle-2", "label": "car", "confidence": .9, "bbox": [135, 110, 220, 190]},
    ]}],
    "candidates": [{"candidate_id": "candidate-0001", "start_s": .8, "end_s": 1.4,
        "representative_s": 1, "person_track_id": "person-1", "vehicle_track_id": "vehicle-2",
        "snapshot": "candidate-0001.jpg", "reason": "Synthetic image proximity for HTTP tests."}],
    "limitations": ["Synthetic test result; not model output."],
}


def fake_runner(source, directory, config, callback):
    assert Path(source).read_bytes() == SOURCE
    assert config["fixed_camera_confirmed"] is True
    callback({"progress": .5})
    (directory / "poster.jpg").write_bytes(b"synthetic JPEG fixture")
    (directory / "candidate-0001.jpg").write_bytes(b"synthetic candidate image")
    (directory / "annotated.avi").write_bytes(b"synthetic AVI fixture")
    return deepcopy(RESULT)


class SafeCrossApiTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.ready = patch("api.safecross_router.readiness", return_value=deepcopy(READY))
        self.ready.start()
        self.addCleanup(self.ready.stop)
        preview = patch("safecross.jobs.VideoJobs._preview", return_value=False)
        preview.start()
        self.addCleanup(preview.stop)
        self.app = self.make_app()
        self.client = self.make_client(self.app)

    def make_app(self):
        app = create_app(
            snapshot_directory=self.directory / "absent-snapshot",
            review_directory=self.directory / "article-review",
            safecross_directory=self.directory / "video-jobs",
            safecross_model_path=self.directory / "absent-model.onnx",
        )
        app.state.safecross_runner = fake_runner
        return app

    def make_client(self, app, *, host="127.0.0.1", base_url="http://127.0.0.1"):
        client = TestClient(app, base_url=base_url, client=(host, 50000))
        client.__enter__()
        self.addCleanup(client.__exit__, None, None, None)
        return client

    def upload(self, **changes):
        data = {"operator": "API test operator", "data_mode": "synthetic", "fixed_camera_confirmed": "true"} | changes
        return self.client.post(f"{API}/jobs", data=data, files={"video": ("synthetic.mp4", SOURCE, "video/mp4")})

    def completed(self, **changes):
        response = self.upload(**changes)
        self.assertEqual(202, response.status_code, response.text)
        job = response.json()
        deadline = time.monotonic() + 5
        while job["status"] in ("queued", "running") and time.monotonic() < deadline:
            time.sleep(.01)
            response = self.client.get(f"{API}/jobs/{job['job_id']}")
            self.assertEqual(200, response.status_code, response.text)
            job = response.json()
        self.assertEqual("completed", job["status"], job)
        return job

    def review(self, job, decision="confirmed", **changes):
        return self.client.post(f"{API}/jobs/{job['job_id']}/candidates/candidate-0001/review", json={
            "expected_version": job["version"], "operator": "Human reviewer", "decision": decision,
            "note": "Synthetic API test: interaction visually checked; not an accident.",
        } | changes)

    def test_page_and_assets_are_available_without_model_or_shared_dataset(self):
        response = self.client.get("/safecross")
        self.assertEqual(200, response.status_code)
        self.assertIn("SafeCross", response.text)
        self.assertIn('lang="ro"', response.text)
        for filename, expected_type in (("app.js", "javascript"), ("styles.css", "text/css")):
            with self.subTest(filename=filename):
                asset = self.client.get(f"/safecross/assets/{filename}")
                self.assertEqual(200, asset.status_code)
                self.assertIn(expected_type, asset.headers["content-type"])
        self.assertEqual(200, self.client.get("/health").status_code)
        self.assertEqual(503, self.client.get("/api/v1/events").status_code)

    def test_status_reports_model_readiness_and_limits(self):
        response = self.client.get(f"{API}/status")
        self.assertEqual(200, response.status_code)
        self.assertEqual(READY, response.json())
        unavailable = deepcopy(READY) | {"available": False, "model_ready": False}
        with patch("api.safecross_router.readiness", return_value=unavailable):
            self.assertFalse(self.client.get(f"{API}/status").json()["model_ready"])
            rejected = self.upload()
        self.assertEqual(503, rejected.status_code, rejected.text)
        self.assertFalse((self.directory / "video-jobs").exists())

    def test_upload_persists_provenance_and_never_publishes_as_accident(self):
        job = self.completed(data_mode="observed", source_url="https://example.org/video", attribution="Test owner", license="Test permission")
        self.assertEqual("observed", job["data_mode"])
        self.assertEqual("not_published", job["publication_status"])
        self.assertEqual("video_observation", job["record_type"])
        self.assertEqual("stored_analysis", job["response_origin"])
        self.assertEqual(sha256(SOURCE).hexdigest(), job["source_sha256"])
        self.assertEqual("Test owner", job["provenance"]["attribution"])
        self.assertEqual("Test permission", job["provenance"]["license"])
        self.assertEqual("https://example.org/video", job["provenance"]["source_url"])
        self.assertEqual("observed", job["result"]["data_mode"])
        self.assertEqual(RESULT["candidates"], job["result"]["candidates"])
        self.assertEqual([], self.client.get("/api/v1/reviewed-events?data_mode=observed").json()["events"])

    def test_camera_confirmation_mode_operator_and_roi_are_validated(self):
        invalid = (
            {"fixed_camera_confirmed": "false"}, {"data_mode": "invented"}, {"operator": ""},
            {"roi_json": "not JSON"}, {"roi_json": "[[0,0],[1,0]]"},
            {"roi_json": "[[0,0],[2,0],[0,1]]"},
            {"roi_json": "[[0,0],[" + str(10**400) + ",0],[0,1]]"},
            {"source_url": "https://["},
        )
        for changes in invalid:
            with self.subTest(changes=changes):
                response = self.upload(**changes)
                self.assertEqual(422, response.status_code, response.text)
        self.assertEqual(422, self.client.post(f"{API}/jobs", data={"operator": "test", "data_mode": "synthetic", "fixed_camera_confirmed": "true"}).status_code)
        job = self.completed(roi_json="[[0,0],[1,0],[0,1]]")
        self.assertEqual([[0, 0], [1, 0], [0, 1]], job["roi"])

    def test_cross_origin_and_nonlocal_access_are_rejected(self):
        foreign = self.make_client(self.app, host="192.0.2.10")
        self.assertEqual(403, foreign.get(f"{API}/status").status_code)
        self.assertEqual(403, self.client.get(f"{API}/status", headers={"Origin": "https://example.org"}).status_code)
        wrong_host = self.make_client(self.app, base_url="http://example.org")
        self.assertEqual(403, wrong_host.get(f"{API}/status").status_code)

    def test_review_requires_current_version_and_preserves_decisions(self):
        job = self.completed()
        response = self.review(job)
        self.assertEqual(200, response.status_code, response.text)
        reviewed = response.json()
        self.assertEqual(job["version"] + 1, reviewed["version"])
        self.assertEqual("confirmed", reviewed["reviews"]["candidate-0001"]["decision"])
        self.assertEqual("Human reviewer", reviewed["reviews"]["candidate-0001"]["operator"])
        self.assertEqual(1, len(reviewed["history"]))
        self.assertEqual("not_published", reviewed["publication_status"])
        self.assertEqual(409, self.review(job, "dismissed").status_code)
        changed = self.review(reviewed, "dismissed")
        self.assertEqual(200, changed.status_code, changed.text)
        self.assertEqual(2, len(changed.json()["history"]))
        self.assertEqual("dismissed", changed.json()["reviews"]["candidate-0001"]["decision"])
        self.assertEqual([], self.client.get("/api/v1/reviewed-events").json()["events"])

    def test_review_rejects_invalid_decisions_and_unknown_candidates(self):
        job = self.completed()
        self.assertEqual(422, self.review(job, "accident").status_code)
        self.assertEqual(422, self.review(job, operator="").status_code)
        response = self.client.post(f"{API}/jobs/{job['job_id']}/candidates/absent/review", json={"expected_version": job["version"], "operator": "Reviewer", "decision": "confirmed", "note": "Synthetic test"})
        self.assertEqual(404, response.status_code, response.text)
        current = self.client.get(f"{API}/jobs/{job['job_id']}").json()
        self.assertEqual(job["version"], current["version"])

    def test_media_supports_ranges_and_serves_only_named_artifacts(self):
        job = self.completed()
        path = f"{API}/jobs/{job['job_id']}/media"
        self.assertEqual(SOURCE, self.client.get(f"{path}/source").content)
        partial = self.client.get(f"{path}/source", headers={"Range": "bytes=0-8"})
        self.assertEqual(206, partial.status_code, partial.text)
        self.assertEqual(SOURCE[:9], partial.content)
        self.assertEqual(200, self.client.get(f"{path}/candidate-0001.jpg").status_code)
        self.assertEqual(200, self.client.get(f"{path}/annotated").status_code)
        for artifact in ("job.json", "absent.jpg", ".env", "../../api/main.py"):
            self.assertEqual(404, self.client.get(f"{path}/{artifact}").status_code, artifact)

    def test_export_labels_mode_preserves_reviews_and_survives_restart(self):
        job = self.completed()
        reviewed = self.review(job).json()
        exported = self.client.get(f"{API}/jobs/{job['job_id']}/export")
        self.assertEqual(200, exported.status_code)
        self.assertIn("synthetic", exported.headers.get("content-disposition", ""))
        self.assertEqual(reviewed["reviews"], exported.json()["reviews"])
        self.assertEqual("not_published", exported.json()["publication_status"])
        restarted = self.make_client(self.make_app())
        restored = restarted.get(f"{API}/jobs/{job['job_id']}")
        self.assertEqual(200, restored.status_code)
        self.assertEqual(reviewed["reviews"], restored.json()["reviews"])
        self.assertEqual("stored_analysis", restored.json()["response_origin"])
        self.assertEqual(404, restarted.get(f"{API}/jobs/absent").status_code)

    def test_source_is_playable_while_worker_waits_and_review_is_blocked(self):
        release = threading.Event()
        self.addCleanup(release.set)
        entered = threading.Event()
        def waiting_runner(source, directory, config, callback):
            (directory / "annotated.avi").write_bytes(b"incomplete synthetic artifact")
            (directory / "candidate-0001.jpg").write_bytes(b"incomplete synthetic snapshot")
            entered.set()
            if not release.wait(5): raise AssertionError("test runner release timed out")
            return fake_runner(source, directory, config, callback)
        self.app.state.safecross_runner = waiting_runner
        response = self.upload()
        self.assertEqual(202, response.status_code, response.text)
        job = response.json()
        self.assertTrue(entered.wait(2))
        source = self.client.get(f"{API}/jobs/{job['job_id']}/media/source")
        self.assertEqual(200, source.status_code, source.text)
        self.assertEqual(SOURCE, source.content)
        self.assertEqual(409, self.review(job).status_code)
        self.assertEqual(409, self.client.get(f"{API}/jobs/{job['job_id']}/media/annotated").status_code)
        self.assertEqual(409, self.client.get(f"{API}/jobs/{job['job_id']}/media/candidate-0001.jpg").status_code)
        release.set()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            current = self.client.get(f"{API}/jobs/{job['job_id']}").json()
            if current["status"] not in ("queued", "running"): break
            time.sleep(.01)
        self.assertEqual("completed", current["status"])

    def test_processing_failure_is_persisted_without_partial_results(self):
        def failing_runner(*args):
            raise SafeCrossError("video_decode_failed", "Synthetic controlled decode failure")
        self.app.state.safecross_runner = failing_runner
        response = self.upload()
        self.assertEqual(202, response.status_code)
        job = response.json()
        deadline = time.monotonic() + 5
        while job["status"] in ("queued", "running") and time.monotonic() < deadline:
            time.sleep(.01)
            job = self.client.get(f"{API}/jobs/{job['job_id']}").json()
        self.assertEqual("failed", job["status"])
        self.assertIsNone(job["result"])
        self.assertEqual("video_decode_failed", job["error"]["code"])

    def test_queue_full_and_oversized_uploads_leave_no_orphaned_jobs(self):
        # Initialize the manager without creating any job directory.
        self.assertEqual(404, self.client.get(f"{API}/jobs/absent").status_code)
        manager = self.app.state.safecross_jobs
        for _ in range(LIMITS["max_queued_jobs"]):
            self.assertTrue(manager.slots.acquire(blocking=False))
        try:
            full = self.upload()
            self.assertEqual(429, full.status_code, full.text)
            self.assertFalse((self.directory / "video-jobs").exists())
        finally:
            for _ in range(LIMITS["max_queued_jobs"]):
                manager.slots.release()
        with patch.dict(LIMITS, {"max_upload_bytes": 8}):
            oversized = self.upload()
        self.assertEqual(413, oversized.status_code, oversized.text)
        folder = self.directory / "video-jobs"
        self.assertEqual([], list(folder.glob("*")))
        # Failure paths must release the queue slot for the next valid request.
        self.assertEqual("completed", self.completed()["status"])

    def test_empty_unsupported_duplicate_and_unknown_upload_fields_are_cleaned_up(self):
        form = {"operator": "Test operator", "data_mode": "synthetic", "fixed_camera_confirmed": "true"}
        cases = [
            ([("video", ("empty.mp4", b"", "video/mp4"))], form, {422}),
            ([("video", ("unsafe.html", SOURCE, "text/html"))], form, {422}),
            ([("video", ("synthetic.mp4", SOURCE, "video/mp4"))], form | {"unknown_field": "unexpected"}, {422}),
            ([("operator", (None, "Duplicate operator")), ("video", ("synthetic.mp4", SOURCE, "video/mp4"))], form, {422}),
            ([("video", ("first.mp4", SOURCE, "video/mp4")), ("video", ("second.mp4", SOURCE, "video/mp4"))], form, {400, 422}),
        ]
        for index, (files, data, allowed_statuses) in enumerate(cases):
            with self.subTest(case=index):
                response = self.client.post(f"{API}/jobs", data=data, files=files)
                self.assertIn(response.status_code, allowed_statuses, response.text)
                folder = self.directory / "video-jobs"
                self.assertEqual([], list(folder.glob("*")))
        self.assertEqual("completed", self.completed()["status"])

    def test_malformed_multipart_returns_client_error_and_keeps_storage_clean(self):
        for content_type, body in (("multipart/form-data", b"no boundary"), ("multipart/form-data; boundary=test-boundary", b"not a multipart payload")):
            with self.subTest(content_type=content_type):
                response = self.client.post(f"{API}/jobs", content=body, headers={"Content-Type": content_type})
                self.assertIn(response.status_code, (400, 422), response.text)
                self.assertEqual([], list((self.directory / "video-jobs").glob("*")))
        self.assertEqual("completed", self.completed()["status"])

    def test_interrupted_job_is_failed_after_restart_without_replaying_inference(self):
        job = self.completed()
        path = self.directory / "video-jobs" / job["job_id"] / "job.json"
        stored = json.loads(path.read_text(encoding="utf-8"))
        stored.update(status="running", result=None, progress=.3)
        path.write_text(json.dumps(stored), encoding="utf-8")
        restarted_app = self.make_app()
        def forbidden_runner(*args):
            raise AssertionError("A restart must not silently replay prior inference")
        restarted_app.state.safecross_runner = forbidden_runner
        restarted = self.make_client(restarted_app)
        restored = restarted.get(f"{API}/jobs/{job['job_id']}")
        self.assertEqual(200, restored.status_code, restored.text)
        self.assertEqual("failed", restored.json()["status"])
        self.assertIsNone(restored.json()["result"])
        self.assertEqual("analysis_interrupted", restored.json()["error"]["code"])
        self.assertEqual("stored_analysis", restored.json()["response_origin"])

    def test_corrupt_saved_json_and_incomplete_records_fail_as_503(self):
        job = self.completed()
        path = self.directory / "video-jobs" / job["job_id"] / "job.json"
        original = path.read_text(encoding="utf-8")
        for contents in ("{broken JSON", "[]", json.dumps({"job_id": job["job_id"], "data_mode": "synthetic"})):
            with self.subTest(contents=contents):
                path.write_text(contents, encoding="utf-8")
                response = self.client.get(f"{API}/jobs/{job['job_id']}")
                self.assertEqual(503, response.status_code, response.text)
                self.assertEqual("video_storage_unavailable", response.json()["detail"]["code"])
                restarted = self.make_client(self.make_app())
                self.assertEqual(503, restarted.get(f"{API}/jobs/{job['job_id']}").status_code)
        path.write_text(original, encoding="utf-8")

    def _wait_for_timing_job(self):
        """Exercise the built-in runner path while keeping external probes mocked."""
        response = self.upload()
        self.assertEqual(202, response.status_code, response.text)
        self.addCleanup(self.app.state.safecross_jobs.executor.shutdown, wait=True)
        job = response.json()
        deadline = time.monotonic() + 5
        while job["status"] in ("queued", "running") and time.monotonic() < deadline:
            time.sleep(.01)
            response = self.client.get(f"{API}/jobs/{job['job_id']}")
            self.assertEqual(200, response.status_code, response.text)
            job = response.json()
        self.assertNotIn(job["status"], ("queued", "running"), job)
        return job

    def test_builtin_runner_rejects_timing_preflight_before_engine_is_called(self):
        self.app.state.safecross_runner = None
        error = SafeCrossError("video_variable_fps", "Synthetic preflight rejected variable timestamps.")
        with patch("safecross.timing.verify_video_timing", side_effect=error) as verify, patch("safecross.engine.analyze_video") as analyze:
            job = self._wait_for_timing_job()
        verify.assert_called_once()
        analyze.assert_not_called()
        self.assertEqual("failed", job["status"])
        self.assertIsNone(job["result"])
        self.assertEqual("video_variable_fps", job["error"]["code"])
        self.assertEqual(409, self.client.get(f"{API}/jobs/{job['job_id']}/export").status_code)

    def test_builtin_runner_rejects_decoder_frame_count_fps_and_geometry_mismatches(self):
        self.app.state.safecross_runner = None
        timing = {"validation": "ffprobe_cfr_verified", "frame_count": 50, "fps": 25, "width": 640, "height": 360}
        for field, value in (("decoded_frame_count", 49), ("fps", 24), ("width", 1280), ("height", 720)):
            with self.subTest(field=field):
                result = deepcopy(RESULT)
                result["video"]["decoded_frame_count"] = 50
                result["video"][field] = value
                with patch("safecross.timing.verify_video_timing", return_value=deepcopy(timing)) as verify, patch("safecross.engine.analyze_video", return_value=result) as analyze:
                    job = self._wait_for_timing_job()
                verify.assert_called_once()
                analyze.assert_called_once()
                self.assertEqual("failed", job["status"])
                self.assertIsNone(job["result"])
                self.assertEqual("video_timing_decoder_mismatch", job["error"]["code"])

    def test_builtin_runner_persists_verified_timing_with_successful_result_and_export(self):
        self.app.state.safecross_runner = None
        timing = {
            "validation": "ffprobe_cfr_verified", "tool": "ffprobe", "frame_count": 50,
            "fps": 25, "frame_rate": "25", "time_base": "1/12800", "first_pts_s": 0,
            "last_pts_s": 1.96, "max_error_s": 0, "tolerance_s": .001,
            "decoded_duration_s": 2, "declared_duration_s": 2, "width": 640, "height": 360,
            "scope": "Synthetic timing mock for orchestration tests only.",
        }
        result = deepcopy(RESULT)
        result["video"]["decoded_frame_count"] = 50
        with patch("safecross.timing.verify_video_timing", return_value=deepcopy(timing)) as verify, patch("safecross.engine.analyze_video", return_value=result) as analyze:
            job = self._wait_for_timing_job()
        verify.assert_called_once()
        analyze.assert_called_once()
        self.assertEqual("completed", job["status"])
        self.assertEqual(timing, job["result"]["timing"])
        self.assertEqual(RESULT["candidates"], job["result"]["candidates"])
        exported = self.client.get(f"{API}/jobs/{job['job_id']}/export")
        self.assertEqual(200, exported.status_code)
        self.assertEqual(timing, exported.json()["result"]["timing"])
        self.assertEqual("not_published", exported.json()["publication_status"])


if __name__ == "__main__":
    unittest.main()
