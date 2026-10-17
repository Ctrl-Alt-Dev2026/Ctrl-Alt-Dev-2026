"""Observed-contract simulations use fictional articles in temporary storage only.

These are integration tests, not a collected or verified accident dataset.
"""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.geocoding import GeocodingError, get_service
from api.main import create_app
from api.review_store import ReviewStore


REPOSITORY = Path(__file__).resolve().parents[1]
ARTICLE = json.loads((REPOSITORY / "false_data/articles.json").read_text(encoding="utf-8"))[0]


class GeocodingWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.app = create_app(review_directory=self.directory / "review", publication_directory=self.directory / "publications")
        self.client = TestClient(self.app, base_url="http://127.0.0.1", client=("127.0.0.1", 53003))
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def candidate(self, text="trecerea de pe Strada Arcu", identifier="one", mode="observed"):
        article = deepcopy(ARTICLE)
        article.update(article_id="test-only-" + identifier, url="https://example.invalid/test-only/" + identifier,
                       sursa="SINTETIC" if mode == "synthetic" else "TEST ONLY - fictional article; observed-contract simulation")
        response = self.client.post("/api/v1/imports", json={"request_id":identifier, "article":article, "data_mode":mode, "operator":"test-only", "pipeline":"rules"})
        self.assertEqual(201, response.status_code, response.text)
        candidate_id = response.json()["import"]["candidate_ids"][0]
        response = self.client.patch("/api/v1/candidates/" + candidate_id, json={"data_mode":mode, "expected_version":1,
            "operator":"test-only", "reason":"Test-only location correction; no factual claim.", "changes":{"loc_text":text}})
        self.assertEqual(200, response.status_code, response.text)
        return response.json()["candidate"]

    def preview(self, candidate):
        response = self.client.post(f"/api/v1/candidates/{candidate['candidate_id']}/geocoding/preview", json={"data_mode":candidate["data_mode"], "expected_version":candidate["version"]})
        self.assertEqual(200, response.status_code, response.text)
        return response.json()["proposal"]

    def apply_body(self, candidate, proposal):
        return {"data_mode":candidate["data_mode"], "expected_version":candidate["version"], "suggestion_id":proposal["suggestion_id"],
                "operator":"test-geocoder", "reason":"Test-only operator checked OSM evidence.", "location_checked":True}

    def apply(self, candidate, proposal):
        response = self.client.post(f"/api/v1/candidates/{candidate['candidate_id']}/geocoding/apply", json=self.apply_body(candidate, proposal))
        self.assertEqual(200, response.status_code, response.text)
        return response.json()["candidate"]

    def test_preview_is_deterministic_read_only_and_apply_archives_provenance_without_approval(self):
        candidate = self.candidate()
        path = self.directory / "review/observed.json"
        before = path.read_bytes()
        proposal = self.preview(candidate)
        self.assertEqual(proposal, self.preview(candidate))
        self.assertEqual(before, path.read_bytes())
        self.assertEqual("trecere", proposal["proposed_changes"]["precizie_loc"])
        self.assertIn("node/2186331539", proposal["report"]["referinte_osm"])
        updated = self.apply(candidate, proposal)
        self.assertEqual(("pending", False, candidate["version"] + 1), (updated["review_status"], updated["verificat"], updated["version"]))
        self.assertEqual(candidate["original_extraction"], updated["original_extraction"])
        archived = updated["history"][-1]["changes"]["geocoding"]["after"]
        self.assertEqual(proposal["report"], archived["report"])
        self.assertEqual(proposal["provenance"], archived["provenance"])
        self.assertTrue(archived["location_checked"])
        restarted = ReviewStore(self.directory / "review", "observed").get_candidate(candidate["candidate_id"])
        self.assertEqual(updated["history"], restarted["history"])

    def test_confirmation_is_strict_and_clients_cannot_supply_coordinates_or_reports(self):
        candidate = self.candidate()
        proposal = self.preview(candidate)
        url = f"/api/v1/candidates/{candidate['candidate_id']}/geocoding/apply"
        for value in (False, "true", 1, None):
            with self.subTest(value=value):
                self.assertEqual(422, self.client.post(url, json=self.apply_body(candidate, proposal) | {"location_checked":value}).status_code)
        self.assertEqual(422, self.client.post(url, json=self.apply_body(candidate, proposal) | {"proposed_changes":{"lat":47.0,"lon":27.0}}).status_code)
        self.assertEqual(409, self.client.post(url, json=self.apply_body(candidate, proposal) | {"suggestion_id":"0" * 64}).status_code)
        self.assertEqual(candidate["version"], ReviewStore(self.directory / "review", "observed").get_candidate(candidate["candidate_id"])["version"])

    def test_stale_version_different_candidate_and_changed_resolver_inputs_reject_tokens(self):
        first = self.candidate()
        proposal = self.preview(first)
        second = self.candidate(identifier="two")
        url = f"/api/v1/candidates/{second['candidate_id']}/geocoding/apply"
        self.assertEqual(409, self.client.post(url, json=self.apply_body(second, proposal)).status_code)
        altered = get_service().suggest(first["fields"]["loc_text"], "observed")
        altered["provenance"] = altered["provenance"] | {"test_only_changed_reference":"different"}
        with patch.object(get_service(), "suggest", return_value=altered):
            url = f"/api/v1/candidates/{first['candidate_id']}/geocoding/apply"
            self.assertEqual(409, self.client.post(url, json=self.apply_body(first, proposal)).status_code)
        updated = self.apply(first, proposal)
        self.assertEqual(409, self.client.post(url, json=self.apply_body(first, proposal)).status_code)
        self.assertEqual(updated["version"], ReviewStore(self.directory / "review", "observed").get_candidate(first["candidate_id"])["version"])

    def test_changing_location_text_invalidates_coordinates_and_proposal_with_audit(self):
        candidate = self.candidate()
        proposal = self.preview(candidate)
        updated = self.apply(candidate, proposal)
        response = self.client.patch(f"/api/v1/candidates/{candidate['candidate_id']}", json={"data_mode":"observed", "expected_version":updated["version"],
            "operator":"test-only", "reason":"New location text needs new evidence.", "changes":{"loc_text":"în zona Gării"}})
        self.assertEqual(200, response.status_code, response.text)
        corrected = response.json()["candidate"]
        for field in ("lat", "lon", "precizie_loc", "in_iasi", "location_evidence"):
            self.assertIsNone(corrected["fields"][field])
            self.assertIn(field, corrected["history"][-1]["changes"])
        self.assertEqual(409, self.client.post(f"/api/v1/candidates/{candidate['candidate_id']}/geocoding/apply", json=self.apply_body(candidate, proposal)).status_code)

    def test_concurrent_apply_has_one_winner_and_dependency_failure_does_not_write(self):
        candidate = self.candidate()
        proposal = self.preview(candidate)
        url = f"/api/v1/candidates/{candidate['candidate_id']}/geocoding/apply"
        before = (self.directory / "review/observed.json").read_bytes()
        with patch.object(get_service(), "suggest", side_effect=GeocodingError(503, "geocoding_unavailable", "Test-only unavailable reference data.")):
            response = self.client.post(url, json=self.apply_body(candidate, proposal))
            self.assertEqual(503, response.status_code)
            self.assertEqual("geocoding_unavailable", response.json()["detail"]["code"])
        self.assertEqual(before, (self.directory / "review/observed.json").read_bytes())
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(lambda _: self.client.post(url, json=self.apply_body(candidate, proposal)).status_code, range(2)))
        self.assertEqual([200, 409], sorted(statuses))

    def test_street_stays_without_precise_coordinates_and_cannot_be_published(self):
        candidate = self.candidate("pe Bulevardul Socola")
        proposal = self.preview(candidate)
        self.assertEqual("strada", proposal["proposed_changes"]["precizie_loc"])
        self.assertIsNone(proposal["proposed_changes"]["lat"])
        updated = self.apply(candidate, proposal)
        response = self.client.post(f"/api/v1/candidates/{candidate['candidate_id']}/review", json={"data_mode":"observed", "expected_version":updated["version"],
            "operator":"test-only", "note":"Test-only contract review.", "action":"approve", "source_checked":True, "duplicate_checked":True, "location_checked":True})
        self.assertEqual(200, response.status_code, response.text)
        event = response.json()["event"]
        body = {"request_id":"street-excluded", "data_mode":"observed", "operator":"test-only", "note":"Test-only publication eligibility.",
            "period_start":"2020-01-01", "period_end":"2026-12-31", "source_conflicts_checked":True,
            "selections":[{"event_id":event["event_id"], "expected_version":event["version"], "location_id":"osm-node-2186331539", "association_checked":True, "association_note":"Test-only association; must be rejected."}]}
        preview = self.client.post("/api/v1/publications/preview", json=body)
        self.assertEqual(200, preview.status_code, preview.text)
        self.assertEqual(1, preview.json()["excluded_event_count"])
        self.assertEqual(422, self.client.post("/api/v1/publications", json=body).status_code)

    def test_synthetic_and_finalized_candidates_never_receive_observed_geocoding(self):
        synthetic = self.candidate(mode="synthetic")
        response = self.client.post(f"/api/v1/candidates/{synthetic['candidate_id']}/geocoding/preview", json={"data_mode":"synthetic", "expected_version":synthetic["version"]})
        self.assertEqual(422, response.status_code)
        self.assertEqual("synthetic_geocoding_unavailable", response.json()["detail"]["code"])
        candidate = self.candidate(identifier="observed")
        proposal = self.preview(candidate)
        updated = self.apply(candidate, proposal)
        response = self.client.post(f"/api/v1/candidates/{candidate['candidate_id']}/review", json={"data_mode":"observed", "expected_version":updated["version"],
            "operator":"test-only", "note":"Test-only review.", "action":"approve", "source_checked":True, "duplicate_checked":True, "location_checked":True})
        self.assertEqual(200, response.status_code, response.text)
        approved = response.json()["candidate"]
        for operation in ("preview", "apply"):
            body = {"data_mode":"observed", "expected_version":approved["version"]} if operation == "preview" else self.apply_body(approved, proposal)
            self.assertEqual(409, self.client.post(f"/api/v1/candidates/{candidate['candidate_id']}/geocoding/{operation}", json=body).status_code)

    def test_crossing_flows_through_explicit_approval_publication_and_dossier(self):
        candidate = self.candidate()
        updated = self.apply(candidate, self.preview(candidate))
        response = self.client.post(f"/api/v1/candidates/{candidate['candidate_id']}/review", json={"data_mode":"observed", "expected_version":updated["version"],
            "operator":"test-only", "note":"Test-only review, not a real accident.", "action":"approve", "source_checked":True, "duplicate_checked":True, "location_checked":True})
        self.assertEqual(200, response.status_code, response.text)
        event = response.json()["event"]
        body = {"request_id":"crossing-published", "data_mode":"observed", "operator":"test-only", "note":"Test-only release in temporary storage; not real accident data.",
            "period_start":"2020-01-01", "period_end":"2026-12-31", "source_conflicts_checked":True,
            "selections":[{"event_id":event["event_id"], "expected_version":event["version"], "location_id":"osm-node-2186331539", "association_checked":True, "association_note":"Test-only check of OSM node identity."}]}
        response = self.client.post("/api/v1/publications", json=body)
        self.assertEqual(201, response.status_code, response.text)
        dossier = self.client.get("/api/v1/locations/osm-node-2186331539?data_mode=observed").json()
        self.assertIsNone(dossier["location"]["score"])
        self.assertEqual(1, len(dossier["events"]))
        archived = dossier["events"][0]["source_claims"][0]["history"][-2]["changes"]["geocoding"]["after"]
        self.assertIn("node/2186331539", archived["report"]["referinte_osm"])
        self.assertEqual(200, self.client.get("/api/v1/locations/osm-node-2186331539/export?data_mode=observed&format=html").status_code)

    def test_geocoding_routes_keep_local_origin_controls_and_startup_lazy(self):
        candidate = self.candidate()
        url = f"/api/v1/candidates/{candidate['candidate_id']}/geocoding/preview"
        body = {"data_mode":"observed", "expected_version":candidate["version"]}
        self.assertEqual(403, self.client.post(url, json=body, headers={"Origin":"https://example.org"}).status_code)
        with patch("api.geocoding.get_service", side_effect=AssertionError("startup must not resolve geography")):
            with TestClient(create_app()) as client:
                self.assertEqual(200, client.get("/health").status_code)
                self.assertIn("/api/v1/candidates/{candidate_id}/geocoding/apply", client.get("/openapi.json").json()["paths"])


if __name__ == "__main__":
    unittest.main()
