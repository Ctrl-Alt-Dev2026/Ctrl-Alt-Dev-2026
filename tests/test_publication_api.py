"""Frontend/map/export contracts against an isolated, fully synthetic release."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.demo_publication import run_demo
from api.main import create_app
from api.publication_router import register_publication, render_dossier


class PublicationApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.directory = Path(cls.temporary.name) / "synthetic-publication"
        cls.proof = run_demo(cls.directory)
        cls.app = create_app(
            snapshot_directory=cls.directory / "legacy-unused",
            review_directory=cls.directory / "review",
            publication_directory=cls.directory / "publications",
            publication_context_directory=cls.directory / "context",
        )
        cls.client = TestClient(cls.app, base_url="http://127.0.0.1", client=("127.0.0.1", 53000))
        cls.client.__enter__()
        cls.addClassCleanup(cls.client.__exit__, None, None, None)

    def test_map_list_dossiers_and_exports_share_version_ids_counts_and_rank(self):
        listing = self.client.get("/api/v1/locations").json()
        geojson = self.client.get("/api/v1/locations.geojson").json()
        self.assertEqual(3, listing["filtered_location_count"])
        self.assertEqual(6, listing["filtered_event_count"])
        self.assertEqual(listing["snapshot_id"], geojson["snapshot_id"])
        self.assertEqual({row["location_id"] for row in listing["locations"]}, {feature["id"] for feature in geojson["features"]})
        self.assertEqual([1, 2, 3], [row["rank"] for row in listing["locations"]])
        for row in listing["locations"]:
            path = "/api/v1/locations/" + row["location_id"]
            dossier = self.client.get(path).json()
            exported = self.client.get(path + "/export")
            self.assertEqual(dossier, exported.json())
            self.assertEqual(row["event_count"], len(dossier["events"]))
            self.assertEqual(listing["snapshot_id"], dossier["snapshot_id"])
            self.assertEqual(row["score"], dossier["location"]["score_details"]["scor"])
            point = next(feature for feature in geojson["features"] if feature["id"] == row["location_id"])
            self.assertEqual(row["feature"]["geometry"], point["geometry"])
            self.assertEqual(row["score"], point["properties"]["score"])
            self.assertEqual(27, int(point["geometry"]["coordinates"][0]))
            self.assertEqual(47, int(point["geometry"]["coordinates"][1]))
            self.assertEqual([], dossier["candidate_measures"])
            self.assertIn("attachment", exported.headers["content-disposition"])

    def test_pagination_and_filters_preserve_published_rank_and_explicit_totals(self):
        whole = self.client.get("/api/v1/locations").json()
        page = self.client.get("/api/v1/locations?limit=1&offset=1").json()
        self.assertEqual(3, page["filtered_location_count"])
        self.assertEqual(1, page["returned_location_count"])
        self.assertEqual(whole["locations"][1], page["locations"][0])
        identifier = page["locations"][0]["location_id"]
        filtered = self.client.get("/api/v1/locations", params={"q": identifier}).json()
        self.assertEqual((1, 2), (filtered["filtered_location_count"], filtered["filtered_event_count"]))
        self.assertEqual(2, filtered["locations"][0]["rank"])
        empty = self.client.get("/api/v1/locations?q=does-not-exist").json()
        self.assertEqual((0, 0, []), (empty["filtered_location_count"], empty["returned_location_count"], empty["locations"]))
        for url in ("/api/v1/locations?limit=0", "/api/v1/locations?offset=-1", "/api/v1/locations?limit=201", "/api/v1/locations?data_mode=unknown"):
            self.assertEqual(422, self.client.get(url).status_code, url)

    def test_observed_mode_and_legacy_snapshot_never_fall_back_to_the_demo(self):
        self.assertEqual(404, self.client.get("/api/v1/locations?data_mode=observed").status_code)
        self.assertEqual(404, self.client.get("/api/v1/publications/latest?data_mode=observed").status_code)
        self.assertEqual(503, self.client.get("/api/v1/events").status_code)
        self.assertEqual(503, self.client.get("/api/v1/manifest").status_code)
        self.assertEqual(503, self.client.get("/api/v1/publication-context?data_mode=observed").status_code)
        self.assertEqual(200, self.client.get("/health").status_code)

    def test_context_pagination_only_proposes_known_locations_without_association(self):
        response = self.client.get("/api/v1/publication-context?data_mode=synthetic&limit=1")
        self.assertEqual(200, response.status_code, response.text)
        context = response.json()
        self.assertEqual((3, 3, 1), (context["total"], context["filtered_total"], len(context["features"])))
        self.assertEqual("synthetic", context["context"]["data_mode"])
        self.assertEqual(1, self.client.get("/api/v1/publication-context?data_mode=synthetic&q=demo-crossing-01").json()["filtered_total"])

    def test_snapshot_pinning_and_canonical_events_keep_all_sources(self):
        snapshot = self.client.get("/api/v1/publications/latest").json()
        snapshot_id = snapshot["snapshot_id"]
        explicit = self.client.get("/api/v1/publications/" + snapshot_id)
        self.assertEqual(snapshot, explicit.json())
        events = self.client.get(f"/api/v1/publications/{snapshot_id}/events").json()
        self.assertEqual(6, len(events["events"]))
        self.assertEqual(7, sum(len(row["source_articles"]) for row in events["events"]))
        listing = self.client.get("/api/v1/locations", params={"snapshot_id": snapshot_id}).json()
        self.assertEqual(snapshot_id, listing["snapshot_id"])
        self.assertEqual(404, self.client.get("/api/v1/publications/not-a-snapshot").status_code)
        self.assertEqual(404, self.client.get("/api/v1/locations/not-a-location").status_code)
        history = self.client.get("/api/v1/publications").json()["publications"]
        self.assertEqual([snapshot_id], [row["snapshot_id"] for row in history])

    def test_explicit_confirmation_versions_and_idempotency_are_enforced_at_http_boundary(self):
        snapshot = self.client.get("/api/v1/publications/latest").json()
        repeated = self.client.post("/api/v1/publications", json=snapshot["request"])
        self.assertEqual(200, repeated.status_code, repeated.text)
        self.assertTrue(repeated.json()["reused"])
        self.assertEqual(snapshot["snapshot_id"], repeated.json()["snapshot"]["snapshot_id"])
        from copy import deepcopy
        body = deepcopy(snapshot["request"])
        body["request_id"] = "http-negative-tests"
        body["source_conflicts_checked"] = False
        self.assertEqual(422, self.client.post("/api/v1/publications", json=body).status_code)
        body["source_conflicts_checked"] = True
        body["selections"][0]["expected_version"] += 1
        self.assertEqual(409, self.client.post("/api/v1/publications/preview", json=body).status_code)
        body["selections"][0]["expected_version"] -= 1
        body["selections"][0]["location_id"] = "missing-location"
        preview = self.client.post("/api/v1/publications/preview", json=body)
        self.assertEqual(200, preview.status_code, preview.text)
        self.assertEqual(1, preview.json()["excluded_event_count"])
        failed = self.client.post("/api/v1/publications", json=body)
        self.assertEqual(422, failed.status_code, failed.text)
        self.assertEqual("ineligible_publication", failed.json()["detail"]["code"])
        self.assertEqual(snapshot, self.client.get("/api/v1/publications/latest").json())

    def test_review_configuration_cannot_write_into_prepared_ai_corpus(self):
        from api.review_store import ReviewError, ReviewStore
        from api.demo_publication import REPOSITORY
        for directory in ("ai/patterns/data/new-review", "context/output/review", "risk/new-review", "coordonate/date_referinta/new-review"):
            with self.subTest(directory=directory), self.assertRaises(ReviewError):
                ReviewStore(REPOSITORY / directory, "synthetic")

    def test_printable_export_escapes_source_and_operator_content_and_uses_no_scripts(self):
        response = self.client.get("/api/v1/locations/demo-crossing-01/export?format=html")
        self.assertEqual(200, response.status_code, response.text)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("DATE SINTETICE".casefold(), response.text.casefold())
        self.assertIn("default-src 'none'", response.headers["content-security-policy"])
        self.assertIn("@media print", response.text)
        dossier = self.client.get("/api/v1/locations/demo-crossing-01").json()
        malicious = '<script>alert(1)</script><img src=x onerror="alert(1)">'
        dossier["location"]["feature"]["properties"]["nume"] = malicious
        dossier["events"][0]["source_articles"][0]["titlu"] = malicious
        dossier["events"][0]["source_articles"][0]["url"] = "javascript:alert(1)"
        dossier["events"][0]["association"]["note"] = malicious
        rendered = render_dossier(dossier)
        self.assertNotIn("<script>", rendered)
        self.assertNotIn("<img", rendered)
        self.assertNotIn('href="javascript:', rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertEqual(422, self.client.get("/api/v1/locations/demo-crossing-01/export?format=pdf").status_code)

    def test_new_publication_writes_and_reads_remain_local_and_same_origin(self):
        for path in ("/api/v1/locations", "/api/v1/publications/latest", "/api/v1/publication-context"):
            self.assertEqual(403, self.client.get(path, headers={"Origin": "https://example.org"}).status_code)
        self.assertEqual(403, self.client.post("/api/v1/publications/preview", json={}, headers={"Origin": "https://example.org"}).status_code)
        self.assertEqual(403, self.client.post("/api/v1/publications", json={}, headers={"Origin": "null"}).status_code)
        with TestClient(self.app, base_url="http://127.0.0.1", client=("192.0.2.1", 53001)) as remote:
            self.assertEqual(403, remote.get("/api/v1/locations").status_code)
        with TestClient(self.app, base_url="http://attacker.example", client=("127.0.0.1", 53002)) as bad_host:
            self.assertEqual(403, bad_host.get("/api/v1/locations").status_code)

    def test_repeated_router_registration_and_health_do_not_load_optional_geometry(self):
        app = create_app()
        before = len(app.routes)
        register_publication(app)
        self.assertEqual(before, len(app.routes))
        with patch("api.publication_context.load_context", side_effect=AssertionError("startup must not load context")):
            with TestClient(app) as client:
                self.assertEqual(200, client.get("/health").status_code)
                self.assertIn("/api/v1/locations", client.get("/openapi.json").json()["paths"])


if __name__ == "__main__":
    unittest.main()
