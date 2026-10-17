"""Review workflow on temporary synthetic data, without any model or shared writes."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from ai.router import get_service
from ai.service import ExtractionService
from api.main import create_app
from api.review_models import CorrectionRequest
from api.review_store import ReviewError, ReviewStore


REPOSITORY = Path(__file__).resolve().parents[1]
ARTICLES = json.loads((REPOSITORY / "false_data/articles.json").read_text(encoding="utf-8"))


class ReviewWorkflowTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name) / "review"
        self.app = create_app(snapshot_directory=Path(temporary.name) / "no-snapshot", review_directory=self.directory)
        self.client = TestClient(self.app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000))
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def body(self, index=0):
        return {"request_id": f"source-{index}", "operator": "test-operator", "data_mode": "synthetic", "article": deepcopy(ARTICLES[index]), "pipeline": "rules"}

    def imported(self, index=0):
        response = self.client.post("/api/v1/imports", json=self.body(index))
        self.assertEqual(201, response.status_code, response.text)
        return response.json()["import"]

    def candidate(self, index=0):
        imported = self.imported(index)
        candidate_id = imported["candidate_ids"][0]
        return self.client.get(f"/api/v1/candidates/{candidate_id}").json()["candidate"]

    def decision(self, version, action="approve", **extra):
        return {"data_mode": "synthetic", "expected_version": version, "operator": "test-reviewer", "note": "Synthetic test: source and event identity checked.", "action": action, "source_checked": True, "duplicate_checked": True} | extra

    def correction(self, version, changes):
        return {"data_mode": "synthetic", "expected_version": version, "operator": "test-reviewer", "reason": "Synthetic manual correction, distinct from original extraction.", "changes": changes}

    def test_import_persists_source_pending_candidates_and_exact_extraction_across_restart(self):
        imported = self.imported()
        self.assertEqual(ARTICLES[0], imported["article"])
        candidate_id = imported["candidate_ids"][0]
        with TestClient(create_app(review_directory=self.directory), base_url="http://127.0.0.1", client=("127.0.0.1", 50001)) as restarted:
            result = restarted.get(f"/api/v1/candidates/{candidate_id}").json()
        self.assertEqual("not_published", result["publication_status"])
        self.assertEqual("stored_review", result["response_origin"])
        record = result["candidate"]
        self.assertEqual("pending", record["review_status"])
        self.assertFalse(record["verificat"])
        self.assertIsNone(record["fields"]["lat"])
        self.assertEqual(imported["extraction"]["candidates"][0], record["original_extraction"])
        self.assertEqual([], self.client.get("/api/v1/reviewed-events").json()["events"])

    def test_retry_is_idempotent_even_after_review_and_never_reinvokes_ai(self):
        record = self.candidate()
        self.assertEqual(200, self.client.post(f"/api/v1/candidates/{record['candidate_id']}/review", json=self.decision(1)).status_code)
        service = Mock()
        service.extract.side_effect = AssertionError("must not re-extract")
        self.app.dependency_overrides[get_service] = lambda: service
        response = self.client.post("/api/v1/imports", json=self.body())
        self.assertEqual(200, response.status_code)
        self.assertTrue(response.json()["reused"])
        current = self.client.get(f"/api/v1/candidates/{record['candidate_id']}").json()["candidate"]
        self.assertEqual("approved", current["review_status"])
        self.assertEqual(1, len(self.client.get("/api/v1/candidates").json()["candidates"]))

    def test_changed_request_or_second_import_of_source_is_a_conflict(self):
        self.imported()
        changed = self.body()
        changed["article"]["text"] += " Changed source revision."
        self.assertEqual(409, self.client.post("/api/v1/imports", json=changed).status_code)
        changed = self.body() | {"request_id": "different-key"}
        self.assertEqual(409, self.client.post("/api/v1/imports", json=changed).status_code)

    def test_correction_keeps_original_evidence_and_records_before_after(self):
        record = self.candidate()
        response = self.client.patch(f"/api/v1/candidates/{record['candidate_id']}", json=self.correction(1, {"ora": None}))
        self.assertEqual(200, response.status_code, response.text)
        corrected = response.json()["candidate"]
        self.assertEqual(2, corrected["version"])
        self.assertIsNone(corrected["fields"]["ora"])
        self.assertEqual(record["original_extraction"], corrected["original_extraction"])
        self.assertEqual({"before": record["fields"]["ora"], "after": None}, corrected["history"][-1]["changes"]["ora"])
        stale = self.client.patch(f"/api/v1/candidates/{record['candidate_id']}", json=self.correction(1, {"ora": "10:00"}))
        self.assertEqual(409, stale.status_code)
        self.assertEqual(409, self.client.post(f"/api/v1/candidates/{record['candidate_id']}/review", json=self.decision(1)).status_code)

    def test_provenance_approval_injection_invalid_dates_and_vague_points_are_rejected(self):
        record = self.candidate()
        for changes in ({"verificat": True}, {"original_extraction": {}}, {"data_eveniment": "2025-02-31"}, {"ora": "25:00"}, {"lat": 47.0}, {"lat": True, "lon": 27.0, "precizie_loc": "trecere"}, {"lat": 47.0, "lon": 27.0, "precizie_loc": "vag"}, {"lat": float('inf'), "lon": 27.0}):
            with self.subTest(changes=changes):
                # A raw payload exercises rejection of nonstandard JSON as well.
                payload = json.dumps(self.correction(1, changes))
                response = self.client.patch(f"/api/v1/candidates/{record['candidate_id']}", content=payload, headers={"Content-Type": "application/json"})
                self.assertEqual(422, response.status_code, response.text)
        self.assertEqual(1, self.client.get(f"/api/v1/candidates/{record['candidate_id']}").json()["candidate"]["version"])

    def test_approval_needs_checks_and_cannot_publish_to_snapshot(self):
        record = self.candidate()
        url = f"/api/v1/candidates/{record['candidate_id']}/review"
        self.assertEqual(422, self.client.post(url, json=self.decision(1, source_checked=False)).status_code)
        response = self.client.post(url, json=self.decision(1))
        self.assertEqual(200, response.status_code, response.text)
        self.assertTrue(response.json()["event"]["verificat"])
        self.assertIsNone(response.json()["event"]["fields"]["lat"])
        self.assertEqual("not_published", response.json()["event"]["publication_status"])
        self.assertEqual(503, self.client.get("/api/v1/events").status_code)
        self.assertEqual(409, self.client.post(url, json=self.decision(2)).status_code)
        self.assertEqual(409, self.client.patch(f"/api/v1/candidates/{record['candidate_id']}", json=self.correction(2, {"ora": None})).status_code)

    def test_pin_requires_location_evidence_and_explicit_review(self):
        record = self.candidate()
        url = f"/api/v1/candidates/{record['candidate_id']}"
        fields = {"lat": 47.0, "lon": 27.0, "precizie_loc": "trecere", "in_iasi": True}
        self.assertEqual(200, self.client.patch(url, json=self.correction(1, fields)).status_code)
        self.assertEqual(422, self.client.post(url + "/review", json=self.decision(2, location_checked=True)).status_code)
        self.assertEqual(200, self.client.patch(url, json=self.correction(2, {"location_evidence": "SYNTHETIC test pin; not an observed location."})).status_code)
        self.assertEqual(422, self.client.post(url + "/review", json=self.decision(3)).status_code)
        self.assertEqual(200, self.client.post(url + "/review", json=self.decision(3, location_checked=True)).status_code)

    def test_rejection_creates_no_canonical_event(self):
        record = self.candidate()
        response = self.client.post(f"/api/v1/candidates/{record['candidate_id']}/review", json=self.decision(1, "reject", source_checked=False, duplicate_checked=False))
        self.assertEqual(200, response.status_code)
        self.assertIsNone(response.json()["event"])
        self.assertFalse(response.json()["candidate"]["verificat"])
        self.assertEqual(1, len(self.client.get("/api/v1/candidates?status=rejected").json()["candidates"]))
        self.assertEqual([], self.client.get("/api/v1/reviewed-events").json()["events"])

    def test_two_articles_link_to_one_event_without_losing_source_claims(self):
        first, second = self.candidate(1), self.candidate(2)
        approved = self.client.post(f"/api/v1/candidates/{first['candidate_id']}/review", json=self.decision(1)).json()["event"]
        link = self.decision(1, "link", canonical_event_id=approved["event_id"], expected_event_version=1)
        self.assertEqual(422, self.client.post(f"/api/v1/candidates/{second['candidate_id']}/review", json={k: v for k, v in link.items() if k != "expected_event_version"}).status_code)
        response = self.client.post(f"/api/v1/candidates/{second['candidate_id']}/review", json=link)
        self.assertEqual(200, response.status_code, response.text)
        events = self.client.get("/api/v1/reviewed-events").json()["events"]
        self.assertEqual(1, len(events))
        event = events[0]
        self.assertEqual(approved["fields"], event["fields"])
        self.assertEqual(["syn-002", "syn-003"], event["article_ids"])
        self.assertEqual(2, len(event["source_claims"]))
        self.assertEqual(2, len(event["urls"]))
        self.assertEqual(second["original_extraction"], event["source_claims"][1]["original_extraction"])
        self.assertIsNone(event["source_claims"][1]["fields"]["ora"])

    def test_link_checks_target_version_and_preserves_pending_candidate_on_conflict(self):
        first, second = self.candidate(1), self.candidate(2)
        event = self.client.post(f"/api/v1/candidates/{first['candidate_id']}/review", json=self.decision(1)).json()["event"]
        response = self.client.post(f"/api/v1/candidates/{second['candidate_id']}/review", json=self.decision(1, "link", canonical_event_id=event["event_id"], expected_event_version=999))
        self.assertEqual(409, response.status_code)
        self.assertEqual("pending", self.client.get(f"/api/v1/candidates/{second['candidate_id']}").json()["candidate"]["review_status"])

    def test_modes_are_separate_and_mismatched_import_is_rejected(self):
        record = self.candidate()
        self.assertEqual([], self.client.get("/api/v1/candidates?data_mode=observed").json()["candidates"])
        self.assertEqual(404, self.client.get(f"/api/v1/candidates/{record['candidate_id']}?data_mode=observed").status_code)
        self.assertEqual(422, self.client.post("/api/v1/imports", json=self.body() | {"data_mode": "observed"}).status_code)
        self.assertTrue((self.directory / "synthetic.json").exists())
        self.assertFalse((self.directory / "observed.json").exists())

    def test_unavailable_provider_never_saves_fallback_and_same_request_can_retry(self):
        service = Mock()
        service.extract.return_value = {"errors": ["offline"], "processing_mode": "rules_fallback", "candidates": []}
        self.app.dependency_overrides[get_service] = lambda: service
        response = self.client.post("/api/v1/imports", json=self.body() | {"pipeline": "hybrid"})
        self.assertEqual(503, response.status_code)
        self.assertFalse(response.json()["persisted"])
        self.assertFalse(self.directory.exists())
        self.app.dependency_overrides.clear()
        self.assertEqual(201, self.client.post("/api/v1/imports", json=self.body()).status_code)

    def test_forged_approval_coordinates_source_or_quote_from_extractor_is_not_saved(self):
        original = ExtractionService().extract(ARTICLES[0], "rules")
        for field, value in (("verificat", True), ("lat", 47.0), ("article_ids", ["invented-source"])):
            broken = deepcopy(original)
            broken["candidates"][0][field] = value
            service = Mock()
            service.extract.return_value = broken
            self.app.dependency_overrides[get_service] = lambda: service
            self.assertEqual(502, self.client.post("/api/v1/imports", json=self.body()).status_code)
        broken = deepcopy(original)
        next(iter(broken["candidates"][0]["evidence_refs"].values()))[0]["quote"] = "Invented quote"
        service.extract.return_value = broken
        self.assertEqual(502, self.client.post("/api/v1/imports", json=self.body()).status_code)
        self.assertFalse(self.directory.exists())

    def test_non_event_article_is_saved_as_import_without_inventing_an_accident(self):
        body = self.body()
        body["article"]["text"] = "Nu a fost implicat niciun pieton. O tamponare între autoturisme."
        response = self.client.post("/api/v1/imports", json=body)
        self.assertEqual(201, response.status_code, response.text)
        self.assertEqual([], response.json()["import"]["candidate_ids"])

    def test_known_negation_false_positive_cannot_become_an_approved_event_on_import(self):
        body = self.body()
        body["article"]["text"] = "Campanie de prevenție pentru pietoni. Nu a avut loc un accident."
        response = self.client.post("/api/v1/imports", json=body)
        self.assertEqual(201, response.status_code)
        for candidate in self.client.get("/api/v1/candidates").json()["candidates"]:
            self.assertEqual("pending", candidate["review_status"])
            self.assertFalse(candidate["verificat"])
        self.assertEqual([], self.client.get("/api/v1/reviewed-events").json()["events"])

    def test_failed_atomic_replace_keeps_previous_file_and_no_partial_correction(self):
        record = self.candidate()
        path = self.directory / "synthetic.json"
        before = path.read_bytes()
        with patch("api.review_store.os.replace", side_effect=OSError("test failure")):
            response = self.client.patch(f"/api/v1/candidates/{record['candidate_id']}", json=self.correction(1, {"ora": None}))
        self.assertEqual(503, response.status_code)
        self.assertEqual(before, path.read_bytes())
        self.assertEqual([], list(self.directory.glob("*.tmp")))
        self.assertEqual(1, self.client.get(f"/api/v1/candidates/{record['candidate_id']}").json()["candidate"]["version"])

    def test_corrupt_store_is_never_overwritten_and_health_still_works(self):
        self.imported()
        path = self.directory / "synthetic.json"
        path.write_text('[broken', encoding="utf-8")
        self.assertEqual(503, self.client.get("/api/v1/candidates").status_code)
        self.assertEqual(503, self.client.post("/api/v1/imports", json=self.body(1)).status_code)
        self.assertEqual('[broken', path.read_text(encoding="utf-8"))
        self.assertEqual(200, self.client.get("/health").status_code)

    def test_concurrent_edits_with_same_version_have_exactly_one_winner(self):
        record = self.candidate()
        store = ReviewStore(self.directory, "synthetic")
        def edit(time):
            try:
                store.correct(record["candidate_id"], CorrectionRequest.model_validate(self.correction(1, {"ora": time})))
                return 200
            except ReviewError as error:
                return error.status
        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses = sorted(executor.map(edit, ("10:00", "11:00")))
        self.assertEqual([200, 409], statuses)
        self.assertEqual(2, store.get_candidate(record["candidate_id"])["version"])

    def test_remote_cross_origin_and_rebinding_requests_cannot_access_review(self):
        self.assertEqual(403, self.client.get("/api/v1/candidates", headers={"Origin": "https://example.com"}).status_code)
        self.assertEqual(403, self.client.get("/api/v1/candidates", headers={"Host": "example.com"}).status_code)
        with TestClient(self.app, base_url="http://127.0.0.1", client=("192.0.2.1", 50000)) as remote:
            self.assertEqual(403, remote.get("/api/v1/candidates").status_code)
        self.assertFalse(self.directory.exists())

    def test_review_directory_cannot_write_into_shared_fixture(self):
        self.app.state.review_directory = REPOSITORY / "false_data"
        response = self.client.post("/api/v1/imports", json=self.body())
        self.assertEqual(503, response.status_code)
        self.assertEqual("protected_review_directory", response.json()["detail"]["code"])
