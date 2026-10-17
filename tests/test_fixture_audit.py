"""Exercise data integrity risks using isolated synthetic documents."""

import json
import tempfile
import unittest
from pathlib import Path

from api.validate_fixtures import audit_fixtures


class FixtureAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.documents = {
            "manifest.json": {
                "schema_version": "2.0", "data_mode": "synthetic",
                "nr_articole": 1, "nr_evenimente": 1,
                "nr_localizate_precis": 0, "nr_verificate": 0,
            },
            "articles.json": [{"article_id": "syn-test-001"}],
            "accidents.json": [{
                "event_id": "syn-event-001", "article_ids": ["syn-test-001"],
                "precizie_loc": "vag", "lat": None, "lon": None,
                "in_iasi": True, "verificat": False, "ora": None,
            }],
            "crossings.geojson": {"type": "FeatureCollection", "features": []},
            "hotspots.json": [], "measure.json": [],
        }

    def write(self):
        for filename, document in self.documents.items():
            (self.directory / filename).write_text(json.dumps(document), encoding="utf-8")

    def codes(self):
        self.write()
        return {item["code"] for item in audit_fixtures(self.directory)["issues"]}

    def test_unknown_location_and_time_pass_without_modifying_files(self):
        self.write()
        before = {path.name: path.read_bytes() for path in self.directory.iterdir()}
        self.assertEqual([], audit_fixtures(self.directory)["issues"])
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.directory.iterdir()})

    def test_observed_data_cannot_pass_a_fixture_audit(self):
        self.documents["manifest.json"]["data_mode"] = "observed"
        self.assertIn("wrong_data_mode", self.codes())

    def test_missing_article_is_reported(self):
        self.documents["accidents.json"][0]["article_ids"] = ["syn-missing"]
        self.assertIn("missing_reference", self.codes())

    def test_event_without_any_source_does_not_pass(self):
        self.documents["accidents.json"][0]["article_ids"] = []
        self.assertIn("missing_reference", self.codes())

    def test_manifest_does_not_override_actual_counts(self):
        self.documents["manifest.json"]["nr_articole"] = 18
        self.assertIn("manifest_count_mismatch", self.codes())

    def test_duplicate_event_ids_do_not_pass(self):
        self.documents["accidents.json"] *= 2
        self.documents["manifest.json"]["nr_evenimente"] = 2
        self.assertIn("duplicate_id", self.codes())

    def test_duplicate_articles_on_an_event_are_reported(self):
        self.documents["accidents.json"][0]["article_ids"] *= 2
        self.assertIn("duplicate_reference", self.codes())

    def test_vague_location_cannot_be_promoted_to_a_point(self):
        self.documents["accidents.json"][0].update(lat=47.0, lon=27.0)
        self.assertIn("vague_point", self.codes())

    def test_invalid_coordinate_and_boolean_are_rejected(self):
        self.documents["accidents.json"][0].update(precizie_loc="trecere", lat=100, lon=True)
        self.assertIn("invalid_coordinates", self.codes())

    def test_location_count_cannot_count_one_event_twice(self):
        self.documents["hotspots.json"] = [{
            "id": "syn-location", "crossing_id": "syn-crossing", "masuri": [],
            "event_ids": ["syn-event-001", "syn-event-001"], "nr_evenimente": 2,
        }]
        self.assertIn("location_count_mismatch", self.codes())

    def test_broken_json_returns_an_actionable_report(self):
        self.write()
        (self.directory / "articles.json").write_text("[", encoding="utf-8")
        report = audit_fixtures(self.directory)
        self.assertEqual("unreadable_json", report["issues"][0]["code"])
        self.assertEqual("articles.json", report["issues"][0]["file"])

    def test_invalid_field_types_are_reported_without_crashing(self):
        self.documents["accidents.json"][0]["precizie_loc"] = []
        self.documents["hotspots.json"] = [{
            "id": "syn-location", "crossing_id": [], "event_ids": [],
            "nr_evenimente": 0, "masuri": [{"measure_id": {}}],
        }]
        codes = self.codes()
        self.assertIn("invalid_precision", codes)
        self.assertIn("missing_reference", codes)

    def test_out_of_range_geojson_point_is_rejected(self):
        self.documents["crossings.geojson"]["features"] = [{
            "type": "Feature", "properties": {"id": "syn-crossing"},
            "geometry": {"type": "Point", "coordinates": [45, 120]},
        }]
        self.assertIn("invalid_coordinates", self.codes())


if __name__ == "__main__":
    unittest.main()
