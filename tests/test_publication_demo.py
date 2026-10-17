"""A real synthetic rehearsal, including duplicate identity and protected inputs."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from api.demo_publication import LOCATIONS, REPOSITORY, prepare_demo, run_demo, synthetic_articles
from api.main import create_app


def fingerprints(paths):
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


class PublicationDemoProtectionTests(unittest.TestCase):
    def test_existing_directory_is_refused_without_touching_its_contents(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            original = directory / "colleague-work.json"
            original.write_bytes(b'{"preserve":true}')
            before = fingerprints([original])
            with self.assertRaises(ValueError):
                prepare_demo(directory)
            self.assertEqual(before, fingerprints([original]))
            self.assertEqual([original], list(directory.iterdir()))

    def test_source_directories_are_protected_even_for_a_new_child(self):
        for relative in ("false_data/demo-should-not-be-created", "ai/benchmarks/demo-should-not-be-created", "api/demo-should-not-be-created"):
            with self.subTest(directory=relative), self.assertRaises(ValueError):
                prepare_demo(REPOSITORY / relative)
            self.assertFalse((REPOSITORY / relative).exists())

    def test_context_hashes_cover_fictional_geometry_and_article_dates_are_separate(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = prepare_demo(Path(temporary) / "fresh")
            manifest = json.loads((directory / "context/publication-context.json").read_text(encoding="utf-8"))
            self.assertEqual("synthetic", manifest["data_mode"])
            for name, digest in manifest["files"].items():
                self.assertEqual(digest, hashlib.sha256((directory / "context" / name).read_bytes()).hexdigest())
            context = json.loads((directory / "context/crossings.geojson").read_text(encoding="utf-8"))
            self.assertEqual(3, len(context["features"]))
            self.assertTrue(all(feature["properties"]["sursa"] == "SINTETIC" for feature in context["features"]))
            articles = synthetic_articles()
            self.assertEqual(7, len(articles))
            self.assertTrue(all(article["sursa"] == "SINTETIC" and "example.invalid/" in article["url"] for article in articles))
            self.assertEqual(articles[0]["text"], articles[6]["text"])
            self.assertNotEqual(articles[0]["publicat_la"], articles[6]["publicat_la"])
            self.assertIn("2026-09-01", articles[0]["text"])
            self.assertEqual("2026-09-02", articles[0]["publicat_la"])


class PublicationDemoWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.directory = Path(cls.temporary.name) / "synthetic-rehearsal"
        protected = list((REPOSITORY / "false_data").rglob("*.json"))
        protected += list((REPOSITORY / "ai/patterns/data").rglob("*"))
        cls.protected = [path for path in protected if path.is_file()]
        cls.before = fingerprints(cls.protected)
        cls.summary = run_demo(cls.directory)

    def test_seven_articles_become_six_events_at_three_locations_without_shared_changes(self):
        self.assertEqual("synthetic", self.summary["data_mode"])
        self.assertEqual("rules", self.summary["processing_mode"])
        self.assertEqual((7, 6, 3), tuple(self.summary[key] for key in ("article_count", "canonical_event_count", "location_count")))
        self.assertTrue(self.summary["duplicate_linked"])
        self.assertEqual(self.before, fingerprints(self.protected))
        self.assertFalse((self.directory / "review/observed.json").exists())
        for location in LOCATIONS:
            dossier = json.loads((self.directory / f"{location['id']}.json").read_text(encoding="utf-8"))
            self.assertEqual(2, len(dossier["events"]))
            self.assertTrue(all(event["fields"]["cauza_raportata"] is None for event in dossier["events"]))
            self.assertTrue(all(event["data_mode"] == "synthetic" for event in dossier["events"]))
            export = self.directory / f"{location['id']}-export.json"
            self.assertEqual(self.summary["dossier_export_sha256"][location["id"]], hashlib.sha256(export.read_bytes()).hexdigest())
            printable = self.directory / f"{location['id']}-export.html"
            self.assertEqual(self.summary["printable_export_sha256"][location["id"]], hashlib.sha256(printable.read_bytes()).hexdigest())
            self.assertIn("SINTETIC", printable.read_text(encoding="utf-8"))
        alfa = json.loads((self.directory / "demo-crossing-01.json").read_text(encoding="utf-8"))
        self.assertEqual([1, 2], sorted(len(event["article_ids"]) for event in alfa["events"]))

    def test_published_snapshot_survives_restart_and_replay_cannot_overwrite_anything(self):
        proof_before = (self.directory / "proof.json").read_bytes()
        with self.assertRaises(ValueError):
            run_demo(self.directory)
        self.assertEqual(proof_before, (self.directory / "proof.json").read_bytes())
        app = create_app(
            snapshot_directory=self.directory / "unused-snapshot", review_directory=self.directory / "review",
            publication_directory=self.directory / "publications", publication_context_directory=self.directory / "context",
        )
        with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 51001)) as client:
            locations = client.get("/api/v1/locations?data_mode=synthetic")
            self.assertEqual(200, locations.status_code, locations.text)
            self.assertEqual(3, len(locations.json()["locations"]))
            events = client.get("/api/v1/reviewed-events?data_mode=synthetic").json()["events"]
            self.assertEqual(6, len(events))
            # Publishing a separate snapshot does not rewrite the review history.
            self.assertTrue(all(event["publication_status"] == "not_published" for event in events))
            self.assertEqual([], client.get("/api/v1/reviewed-events?data_mode=observed").json()["events"])
