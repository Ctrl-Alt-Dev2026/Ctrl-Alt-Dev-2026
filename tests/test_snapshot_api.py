"""Synthetic snapshot integration tests; no real accident data is created."""

from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import create_app
from api.snapshots import SnapshotError, load_snapshot


class SnapshotApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        events = [{
            "event_id": f"syn-event-{n}", "article_ids": [f"syn-article-{n}"],
            "urls": [f"https://example.com/synthetic-{n}"],
            "data_eveniment": "2025-03-12", "ora": None,
            "loc_text": "Locatie SINTETICA pentru test", "precizie_loc": "trecere",
            "lat": 47.0, "lon": 27.0, "in_iasi": True, "verificat": True,
            "gravitate": "necunoscut", "internal_note": "not part of the public contract",
        } for n in range(1, 8)]
        events[0]["article_ids"].append("syn-article-8")
        events[0]["urls"].append("https://example.com/synthetic-8")
        events[1]["verificat"] = False
        events[2].update(precizie_loc="vag", lat=None, lon=None)
        events[3]["in_iasi"] = False
        events[4]["data_eveniment"] = "2023-01-01"
        events[5]["data_eveniment"] = None
        events[6]["precizie_loc"] = "strada"
        self.documents = {
            "manifest.json": {
                "schema_version": "2.0", "data_mode": "synthetic",
                "perioada": ["2024-10-01", "2026-10-17"],
                "generat_la": "2026-10-17T16:00:00+03:00",
                "nr_articole": 8, "nr_evenimente": 7,
                "nr_localizate_precis": 4, "nr_verificate": 6,
            },
            "articles.json": [{
                "article_id": f"syn-article-{n}", "sursa": "SINTETIC",
                "url": f"https://example.com/synthetic-{n}", "publicat_la": "2026-10-17",
            } for n in range(1, 9)],
            "accidents.json": events,
            "crossings.geojson": {"type": "FeatureCollection", "features": []},
            "hotspots.json": [], "measure.json": [],
        }

    def write(self):
        for filename, document in self.documents.items():
            (self.directory / filename).write_text(json.dumps(document), encoding="utf-8")

    def client(self):
        return TestClient(create_app(self.directory))

    def test_valid_snapshot_filters_events_and_keeps_sources_unknowns_and_mode(self):
        self.write()
        before = {path.name: path.read_bytes() for path in self.directory.iterdir()}
        with self.client() as client:
            manifest_response = client.get("/api/v1/manifest")
            events_response = client.get("/api/v1/events")
        self.assertEqual(200, manifest_response.status_code)
        self.assertEqual(200, events_response.status_code)
        manifest, payload = manifest_response.json(), events_response.json()
        self.assertEqual(manifest["snapshot_id"], payload["snapshot_id"])
        self.assertEqual("synthetic", payload["data_mode"])
        self.assertIn("DATE SINTETICE", payload["warning"])
        self.assertEqual(7, manifest["manifest"]["nr_evenimente"])
        self.assertEqual(1, manifest["eligible_event_count"])
        self.assertEqual(["syn-event-1"], [event["event_id"] for event in payload["events"]])
        event = payload["events"][0]
        self.assertEqual(2, len(event["article_ids"]))
        self.assertIsNone(event["ora"])
        self.assertEqual("necunoscut", event["gravitate"])
        self.assertNotIn("internal_note", event)
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.directory.iterdir()})

    def test_missing_files_do_not_prevent_health_but_data_routes_return_503(self):
        with self.client() as client:
            self.assertEqual(200, client.get("/health").status_code)
            for route in ("/api/v1/manifest", "/api/v1/events"):
                response = client.get(route)
                self.assertEqual(503, response.status_code)
                self.assertEqual("snapshot_unavailable", response.json()["detail"]["code"])
                self.assertNotIn(str(self.directory), response.text)

    def test_bad_counts_block_all_data_without_returning_partial_events(self):
        self.documents["manifest.json"]["nr_articole"] = 18
        self.write()
        with self.client() as client:
            for route in ("/api/v1/manifest", "/api/v1/events"):
                response = client.get(route)
                self.assertEqual(503, response.status_code)
                self.assertEqual("invalid_snapshot", response.json()["detail"]["code"])
                self.assertNotIn("events", response.json())

    def test_observed_data_is_not_published_via_synthetic_reader(self):
        self.documents["manifest.json"]["data_mode"] = "observed"
        self.write()
        with self.client() as client:
            response = client.get("/api/v1/events")
        self.assertEqual(503, response.status_code)
        self.assertEqual("unsupported_data_mode", response.json()["detail"]["code"])

    def test_marked_duplicates_require_canonicalization_instead_of_losing_sources(self):
        self.documents["accidents.json"][0]["duplicate_of"] = "syn-event-2"
        self.write()
        with self.client() as client:
            response = client.get("/api/v1/events")
        self.assertEqual(503, response.status_code)
        self.assertIn("noncanonical_event", {item["code"] for item in response.json()["detail"]["issues"]})

    def test_invalid_json_duplicate_object_keys_and_nan_are_rejected(self):
        for contents in ("[", '{"x":NaN}', '{"x":1e999}', '{"x":"\\ud800"}', '{"x":1,"x":2}'):
            with self.subTest(contents=contents):
                self.write()
                (self.directory / "articles.json").write_text(contents, encoding="utf-8")
                with self.client() as client:
                    response = client.get("/api/v1/manifest")
                self.assertEqual(503, response.status_code)
                self.assertEqual("invalid_json", response.json()["detail"]["issues"][0]["code"])

    def test_extreme_coordinate_is_rejected_without_crashing_health(self):
        self.documents["accidents.json"][0]["lon"] = 10 ** 400
        self.write()
        with self.client() as client:
            self.assertEqual(200, client.get("/health").status_code)
            response = client.get("/api/v1/events")
        self.assertEqual(503, response.status_code)
        self.assertEqual("invalid_snapshot", response.json()["detail"]["code"])

    def test_invalid_period_timestamp_or_event_date_is_rejected(self):
        original = deepcopy(self.documents)
        changes = (
            ("manifest.json", "perioada", ["2026-10-17", "2024-10-01"]),
            ("manifest.json", "generat_la", "2026-10-17T16:00:00"),
            ("accidents.json", "data_eveniment", "2025-02-31"),
        )
        for filename, field, value in changes:
            with self.subTest(field=field):
                self.documents = deepcopy(original)
                target = self.documents[filename]
                (target[0] if isinstance(target, list) else target)[field] = value
                self.write()
                with self.client() as client:
                    response = client.get("/api/v1/events")
                self.assertEqual(503, response.status_code)
                self.assertEqual("invalid_snapshot", response.json()["detail"]["code"])

    def test_loaded_version_is_stable_until_restart(self):
        self.write()
        with self.client() as client:
            first = client.get("/api/v1/events").json()
            (self.directory / "accidents.json").write_text("[", encoding="utf-8")
            self.assertEqual(first, client.get("/api/v1/events").json())
        with self.client() as restarted:
            self.assertEqual(503, restarted.get("/api/v1/events").status_code)

    def test_configuration_uses_explicit_snapshot_directory(self):
        self.write()
        with patch.dict(os.environ, {"SAFEIASI_SNAPSHOT_DIR": str(self.directory)}):
            configured = create_app()
        with TestClient(configured) as client:
            self.assertEqual(200, client.get("/api/v1/manifest").status_code)

    def test_snapshot_changed_during_read_is_rejected(self):
        self.write()
        original_read = Path.read_bytes

        def read_and_change(path):
            contents = original_read(path)
            if path.name == "articles.json":
                with (self.directory / "manifest.json").open("a", encoding="utf-8") as file:
                    file.write(" ")
            return contents

        with patch.object(Path, "read_bytes", read_and_change):
            with self.assertRaises(SnapshotError) as result:
                load_snapshot(self.directory)
        self.assertEqual("snapshot_changed", result.exception.code)


if __name__ == "__main__":
    unittest.main()
