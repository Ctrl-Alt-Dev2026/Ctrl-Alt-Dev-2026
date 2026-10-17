"""Isolated infrastructure contracts and parity with the team's risk formula."""

from copy import deepcopy
import hashlib
import json
import marshal
from pathlib import Path
import tempfile
from types import FunctionType
import unittest
from unittest.mock import patch

from api.publication_context import DEFAULT_CONTEXT, PublicationContextError, load_context, score_location, scorer_provenance


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def synthetic_context(directory):
    boundary = {"type": "Feature", "properties": {"sursa": "SINTETIC"}, "geometry": {
        "type": "Polygon", "coordinates": [[[27.57, 47.15], [27.60, 47.15], [27.60, 47.18], [27.57, 47.18], [27.57, 47.15]]],
    }}
    features = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [27.58, 47.17]},
                 "properties": {"id": "synthetic-crossing", "tip": "trecere", "nume": "Exemplu sintetic",
                                "sursa": "SINTETIC", "descarcat_la": "2026-10-17", "semafor": False, "benzi": 4,
                                "iluminat": None, "tip_strada": None, "scoala_150m": True, "statie_100m": None}}]
    write_json(directory / "boundary.geojson", boundary)
    write_json(directory / "crossings.geojson", {"type": "FeatureCollection", "features": features})
    refresh_manifest(directory)
    return boundary, features


def refresh_manifest(directory, **overrides):
    manifest = {"schema_version": "publication-context-1", "data_mode": "synthetic",
                "provenance": "Fixture geometric sintetic, fără pretenții despre infrastructura reală.",
                "generated_at": "2026-10-17T17:00:00+03:00",
                "files": {name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
                          for name in ("boundary.geojson", "crossings.geojson")}}
    manifest.update(overrides)
    write_json(directory / "publication-context.json", manifest)


def event(**changes):
    return {"event_id": "synthetic-event-1", "data_mode": "synthetic", "in_iasi": True,
            "precizie_loc": "trecere", "lon": 27.58, "lat": 47.17, "gravitate": "necunoscut",
            "ora": None, "noapte": None, "cauza_raportata": None, **changes}


class PublicationContextTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.boundary, self.features = synthetic_context(self.directory)

    def load(self):
        return load_context(self.directory, "synthetic")

    def update_crossings(self, features):
        write_json(self.directory / "crossings.geojson", {"type": "FeatureCollection", "features": features})
        refresh_manifest(self.directory)

    def test_provenance_hashes_stable_fingerprint_and_returned_copies(self):
        context = self.load()
        metadata = context.metadata
        self.assertEqual("synthetic", metadata["data_mode"])
        self.assertEqual(1, metadata["location_count"])
        self.assertEqual(64, len(metadata["fingerprint"]))
        self.assertIn("+00:00", metadata["loaded_at"])
        self.assertIn("Fixture geometric sintetic", metadata["provenance"])
        self.assertEqual(metadata["fingerprint"], self.load().metadata["fingerprint"])
        for name, digest in metadata["file_hashes"].items():
            self.assertEqual(digest, hashlib.sha256((self.directory / name).read_bytes()).hexdigest())
        metadata["file_hashes"].clear()
        feature = context.feature("synthetic-crossing")
        feature["geometry"]["coordinates"][0] = 1
        context.all_features()[0]["properties"]["semafor"] = True
        self.assertEqual([27.58, 47.17], context.feature("synthetic-crossing")["geometry"]["coordinates"])
        self.assertFalse(context.feature("synthetic-crossing")["properties"]["semafor"])
        self.assertEqual(3, len(context.metadata["file_hashes"]))

    def test_unknown_osm_values_remain_unknown_and_score_matches_existing_formula(self):
        from risk.pipeline import score_location as existing
        context = self.load()
        feature = context.feature("synthetic-crossing")
        events = [event(), event(event_id="synthetic-event-2", gravitate="deces", ora="23:30")]
        original_feature, original_events = deepcopy(feature), deepcopy(events)
        actual = context.score(feature, events)
        self.assertEqual(existing(feature, events), actual)
        self.assertEqual(9, actual["scor"])
        self.assertEqual(["synthetic-event-1", "synthetic-event-2"], actual["event_ids"])
        self.assertIn("iluminat necunoscut", actual["date_lipsa"])
        self.assertEqual(original_feature, feature)
        self.assertEqual(original_events, events)
        self.assertEqual(actual, context.score_location("synthetic-crossing", events))

    def test_scorer_provenance_binds_actual_loaded_code_to_current_source(self):
        from risk.pipeline import score_location as existing
        provenance = scorer_provenance()
        self.assertEqual(hashlib.sha256(Path(existing.__code__.co_filename).read_bytes()).hexdigest(), provenance["source_sha256"])
        self.assertEqual(hashlib.sha256(marshal.dumps(existing.__code__)).hexdigest(), provenance["callable_sha256"])
        self.assertEqual("risk.pipeline.score_location", provenance["function_name"])
        self.assertRegex(provenance["python_version"], r"^3\.\d+\.\d+")

    def test_changed_source_or_loaded_code_refuses_score_before_any_calculation(self):
        from risk.pipeline import score_location as existing
        context = self.load()
        feature = context.feature("synthetic-crossing")
        source = Path(existing.__code__.co_filename).read_bytes()
        changed_source = source.replace(b"components['context'] += 2", b"components['context'] += 3")
        self.assertNotEqual(source, changed_source)
        with patch.object(Path, "read_bytes", return_value=changed_source), patch("api.publication_context.score_location") as calculation:
            with self.assertRaises(PublicationContextError) as caught:
                context.score(feature, [event()])
            self.assertEqual("scorer_changed_restart_required", caught.exception.code)
            calculation.assert_not_called()
        changed_code = existing.__code__.replace(co_consts=existing.__code__.co_consts + ("changed-test-code",))
        changed_function = FunctionType(changed_code, existing.__globals__, existing.__name__, existing.__defaults__, existing.__closure__)
        with patch("risk.pipeline.score_location", changed_function), patch("api.publication_context.score_location") as calculation:
            with self.assertRaises(PublicationContextError) as caught:
                context.score(feature, [event()])
            self.assertEqual("scorer_changed_restart_required", caught.exception.code)
            calculation.assert_not_called()

    def test_checks_require_explicit_city_precision_and_nearby_coordinates(self):
        context = self.load()
        self.assertEqual([], context.check_event(event(), "synthetic-crossing"))
        self.assertEqual(["in_iasi_not_confirmed"], context.check_event(event(in_iasi=None), "synthetic-crossing"))
        self.assertEqual(["precision_mismatch"], context.check_event(event(precizie_loc="segment"), "synthetic-crossing"))
        self.assertEqual(["data_mode_mismatch"], context.check_event(event(data_mode="observed"), "synthetic-crossing"))
        self.assertEqual(["coordinates_missing"], context.check_event(event(lon=None), "synthetic-crossing"))
        self.assertEqual(["invalid_coordinates"], context.check_event(event(lon=True), "synthetic-crossing"))
        self.assertEqual(["location_too_far"], context.check_event(event(lon=27.59), "synthetic-crossing"))
        self.assertEqual(["outside_iasi_boundary"], context.check_event(event(lon=47.17, lat=27.58), "synthetic-crossing"))
        self.assertEqual(["invalid_coordinates"], context.check_event(event(lon=10 ** 400), "synthetic-crossing"))
        self.assertEqual(["outside_iasi_boundary"], context.check_event(event(lon=180, lat=90), "synthetic-crossing"))

    def test_unknown_location_and_scoring_a_modified_location_are_refused(self):
        context = self.load()
        self.assertEqual(["location_not_found"], context.check_event(event(), "missing"))
        with self.assertRaises(PublicationContextError) as caught:
            context.feature("missing")
        self.assertEqual(404, caught.exception.status_code)
        feature = context.feature("synthetic-crossing")
        feature["properties"]["semafor"] = True
        with self.assertRaises(PublicationContextError):
            context.score(feature, [event()])
        with self.assertRaises(PublicationContextError):
            score_location(context.feature("synthetic-crossing"), [event(), event()])

    def test_manifest_requires_explicit_mode_schema_provenance_time_and_hashes(self):
        for override in ({"schema_version": "other"}, {"data_mode": "observed"}, {"provenance": " "},
                         {"generated_at": "2026-10-17T17:00:00"}, {"files": {}}, {"extra": True}):
            with self.subTest(override=override):
                refresh_manifest(self.directory, **override)
                with self.assertRaises(PublicationContextError):
                    self.load()
        refresh_manifest(self.directory)
        (self.directory / "crossings.geojson").write_text("{}", encoding="utf-8")
        with self.assertRaises(PublicationContextError):
            self.load()

    def test_synthetic_and_observed_modes_cannot_share_an_implicit_context(self):
        with self.assertRaises(PublicationContextError):
            load_context(self.directory, "observed")
        with self.assertRaises(PublicationContextError):
            load_context(self.directory, "both")
        features = deepcopy(self.features)
        features[0]["properties"]["sursa"] = "OSM"
        self.update_crossings(features)
        with self.assertRaises(PublicationContextError):
            self.load()

    def test_duplicate_ids_malformed_tristates_outside_locations_and_point_only(self):
        variants = []
        duplicate = deepcopy(self.features) * 2
        variants.append(duplicate)
        for field, value in (("semafor", 0), ("benzi", True), ("benzi", 0), ("descarcat_la", "2026-02-30")):
            features = deepcopy(self.features)
            features[0]["properties"][field] = value
            variants.append(features)
        for geometry in ({"type": "Point", "coordinates": [27.61, 47.17]},
                         {"type": "Point", "coordinates": [47.17, 27.58]},
                         {"type": "Point", "coordinates": [27.58, 47.17, 2]},
                         {"type": "LineString", "coordinates": [[27.58, 47.17], [27.59, 47.17]]}):
            features = deepcopy(self.features)
            features[0]["geometry"] = geometry
            variants.append(features)
        for features in variants:
            with self.subTest(features=features):
                self.update_crossings(features)
                with self.assertRaises(PublicationContextError):
                    self.load()

    def test_invalid_or_swapped_boundary_and_missing_file_refused(self):
        for coordinates in ([[[47.15, 27.57], [47.15, 27.60], [47.18, 27.60], [47.18, 27.57], [47.15, 27.57]]],
                            [[[27.57, 47.15], [27.60, 47.18], [27.60, 47.15], [27.57, 47.18], [27.57, 47.15]]]):
            boundary = deepcopy(self.boundary)
            boundary["geometry"]["coordinates"] = coordinates
            write_json(self.directory / "boundary.geojson", boundary)
            refresh_manifest(self.directory)
            with self.assertRaises(PublicationContextError):
                self.load()
        (self.directory / "boundary.geojson").unlink()
        with self.assertRaises(PublicationContextError) as caught:
            self.load()
        self.assertEqual("publication_context_unavailable", caught.exception.code)

    def test_duplicate_json_keys_and_float_overflow_refused(self):
        for text in ('{"type":"FeatureCollection","type":"FeatureCollection","features":[]}',
                     '{"bad":1e9999}', '{"bad":NaN}'):
            (self.directory / "crossings.geojson").write_text(text, encoding="utf-8")
            refresh_manifest(self.directory)
            with self.assertRaises(PublicationContextError):
                self.load()

    def test_multipolygon_is_accepted_and_holes_do_not_become_event_locations(self):
        boundary = deepcopy(self.boundary)
        outer = boundary["geometry"]["coordinates"]
        hole = [[27.585, 47.155], [27.595, 47.155], [27.595, 47.165], [27.585, 47.165], [27.585, 47.155]]
        boundary["geometry"] = {"type": "MultiPolygon", "coordinates": [[outer[0], hole]]}
        write_json(self.directory / "boundary.geojson", boundary)
        refresh_manifest(self.directory)
        context = self.load()
        self.assertEqual([], context.check_event(event(), "synthetic-crossing"))
        self.assertEqual(["outside_iasi_boundary"], context.check_event(event(lon=27.59, lat=47.16), "synthetic-crossing"))

    def test_giant_integer_infrastructure_coordinates_are_rejected_cleanly(self):
        features = deepcopy(self.features)
        features[0]["geometry"]["coordinates"] = [10 ** 400, 47.17]
        self.update_crossings(features)
        with self.assertRaises(PublicationContextError):
            self.load()

    def test_midread_change_is_detected(self):
        original = Path.read_bytes
        changed = False
        def mutation(path):
            nonlocal changed
            content = original(path)
            if path.name == "crossings.geojson" and not changed:
                changed = True
                path.write_bytes(content + b" ")
            return content
        with patch.object(Path, "read_bytes", mutation), self.assertRaises(PublicationContextError) as caught:
            self.load()
        self.assertEqual("publication_context_changed", caught.exception.code)

    def test_default_observed_context_and_evidence_preserve_unknowns(self):
        context = load_context(DEFAULT_CONTEXT, "observed")
        self.assertEqual(1210, context.metadata["location_count"])
        self.assertEqual(1207838, context.metadata["boundary_relation_id"])
        self.assertIn("OpenStreetMap", context.metadata["attribution"])
        feature = context.feature("osm-node-31200246")
        self.assertIsNone(feature["properties"]["semafor"])
        self.assertIsNone(feature["properties"]["scoala_150m"])
        self.assertEqual([], context.check_event(event(data_mode="observed", lon=27.6092823, lat=47.1777028), "osm-node-31200246"))
        with self.assertRaises(PublicationContextError):
            load_context(DEFAULT_CONTEXT, "synthetic")

    def test_observed_tags_and_poi_absence_require_the_original_evidence(self):
        documents = {name: json.loads((DEFAULT_CONTEXT / name).read_text(encoding="utf-8"))
                     for name in ("boundary.geojson", "crossings.geojson", "geometry_report.json")}
        # Small read-only copy keeps the real municipality polygon/provenance,
        # but tests only one location without modifying the team's export.
        documents["crossings.geojson"]["features"] = documents["crossings.geojson"]["features"][:1]
        documents["geometry_report.json"]["crossings"] = documents["geometry_report.json"]["crossings"][:1]
        for name, document in documents.items():
            write_json(self.directory / name, document)
        context = load_context(self.directory, "observed")
        self.assertEqual(1, context.metadata["location_count"])
        for mutation in ("invented_absence", "invalid_tag", "giant_distance", "wrong_location_type"):
            with self.subTest(mutation=mutation):
                crossings, report = deepcopy(documents["crossings.geojson"]), deepcopy(documents["geometry_report.json"])
                if mutation == "invented_absence":
                    crossings["features"][0]["properties"]["scoala_150m"] = False
                elif mutation == "invalid_tag":
                    report["crossings"][0]["crossing_tags"]["crossing"] = []
                elif mutation == "wrong_location_type":
                    crossings["features"][0]["properties"]["tip"] = "intersectie"
                else:
                    report["crossings"][0]["schools_150m"] = [{"distance_m": 10 ** 400}]
                    crossings["features"][0]["properties"]["scoala_150m"] = True
                write_json(self.directory / "crossings.geojson", crossings)
                write_json(self.directory / "geometry_report.json", report)
                with self.assertRaises(PublicationContextError):
                    load_context(self.directory, "observed")


if __name__ == "__main__":
    unittest.main()
