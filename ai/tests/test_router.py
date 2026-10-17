import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from ai.app import app, create_app
from ai.router import get_service
from ai.service import ExtractionService

ARTICLE = json.loads((Path(__file__).resolve().parents[1] / "benchmarks/source_articles.json").read_text(encoding="utf-8"))[0]


class RouterTests(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides.clear()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()

    def test_backend_health_root_and_docs_are_preserved(self):
        with patch("ai.router.ExtractionService", side_effect=AssertionError("health must not instantiate AI")):
            self.assertEqual({"status": "ok", "service": "safeiasi-api"}, self.client.get("/health").json())
            self.assertEqual(307, self.client.get("/", follow_redirects=False).status_code)
        schema = self.client.get("/openapi.json").json()
        self.assertIn("/health", schema["paths"])
        self.assertIn("/api/v1/ai/extract", schema["paths"])

    def test_rules_extraction_and_legacy_alias_share_one_handler(self):
        body = {"article": ARTICLE, "pipeline": "rules"}
        response = self.client.post("/api/v1/ai/extract", json=body)
        self.assertEqual(200, response.status_code)
        self.assertEqual(response.json(), self.client.post("/extract", json=body).json())
        self.assertEqual("2.0", response.json()["schema_version"])
        self.assertEqual("pending", response.json()["candidates"][0]["review_status"])

    def test_invalid_contract_and_untrusted_coordinates_are_422(self):
        for article in ({"text": "incomplete"}, {**ARTICLE, "lat": 47.0}):
            self.assertEqual(422, self.client.post("/extract", json={"article": article}).status_code)

    def test_replay_get_and_post_are_explicit_and_cwd_independent(self):
        get = self.client.get("/api/v1/ai/replays/syn-003")
        post = self.client.post("/extract", json={"mode": "replay", "article_id": "syn-003"})
        self.assertEqual(200, get.status_code)
        self.assertEqual(get.json(), post.json())
        self.assertIn("SYNTHETIC REPLAY", get.json()["label"])
        self.assertEqual(404, self.client.get("/api/v1/ai/replays/absent").status_code)

    def test_provider_failure_is_503_with_pending_diagnostics(self):
        client = Mock()
        client.extract.side_effect = RuntimeError("provider offline")
        service = ExtractionService(client=client)
        app.dependency_overrides[get_service] = lambda: service
        response = self.client.post("/extract", json={"article": ARTICLE})
        self.assertEqual(503, response.status_code)
        self.assertEqual("rules_fallback", response.json()["processing_mode"])
        self.assertFalse(response.json()["candidates"][0]["verificat"])

    def test_unknown_pipeline_is_rejected_before_execution(self):
        response = self.client.post("/extract", json={"article": ARTICLE, "pipeline": "not-a-pipeline"})
        self.assertEqual(422, response.status_code)

    def test_backend_snapshot_errors_do_not_block_pending_extraction(self):
        repository = Path(__file__).resolve().parents[2]
        with TestClient(create_app(repository / "false_data")) as client:
            self.assertEqual(200, client.get("/health").status_code)
            before = client.get("/api/v1/events")
            self.assertEqual(503, before.status_code)
            self.assertEqual("invalid_snapshot", before.json()["detail"]["code"])
            response = client.post("/extract", json={"article": ARTICLE, "pipeline": "rules"})
            self.assertEqual(200, response.status_code)
            self.assertFalse(response.json()["candidates"][0]["verificat"])
            self.assertEqual(before.json(), client.get("/api/v1/events").json())

    def test_factory_preserves_snapshot_lifespan_and_extraction_cannot_publish(self):
        from api.snapshots import Snapshot
        snapshot = Snapshot("sha256:synthetic-integration-test", {"schema_version": "2.0", "data_mode": "synthetic"},
                            ({"event_id": "synthetic-existing-reviewed", "verificat": True},))
        with patch("api.main.load_snapshot", return_value=snapshot) as loader:
            with TestClient(create_app("unused-synthetic-test-directory")) as client:
                first = client.get("/api/v1/events")
                self.assertEqual(200, first.status_code)
                self.assertEqual(1, first.json()["eligible_event_count"])
                self.assertEqual(200, client.post("/extract", json={"article": ARTICLE, "pipeline": "rules"}).status_code)
                self.assertEqual(first.json(), client.get("/api/v1/events").json())
                self.assertEqual(first.json()["snapshot_id"], client.get("/api/v1/manifest").json()["snapshot_id"])
            loader.assert_called_once()
