"""Offline geocoding proposals never become approved coordinates by themselves."""

from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from api.geocoding import GeocodingError, GeocodingService, get_service
from api.review_models import CandidateFields


REFERENCES = Path(__file__).resolve().parents[1] / "coordonate/date_referinta"
FILES = ("osm/index_osm.json.gz", "osm/unitati_admin.geojson", "alias_nume.json", "noduri_cunoscute.json")


class GeocodingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = GeocodingService()
        cls.before = {name: hashlib.sha256((REFERENCES / name).read_bytes()).hexdigest() for name in FILES}
        cls.arcu = cls.service.suggest("trecerea de pe Strada Arcu", "observed")

    def assert_error(self, callable, *args):
        with self.assertRaises(GeocodingError) as caught:
            callable(*args)
        return caught.exception

    def copy_inputs(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        (directory / "osm").mkdir()
        for name in FILES:
            shutil.copyfile(REFERENCES / name, directory / name)
        return directory

    def test_factory_and_constructor_do_not_read_files_or_load_reference_data(self):
        get_service.cache_clear()
        with patch.object(Path, "read_bytes", side_effect=AssertionError("no IO")), patch.object(Path, "resolve", side_effect=AssertionError("no path IO")):
            service = get_service()
            self.assertIsInstance(service, GeocodingService)
            self.assertIsNone(service._resolver)
            self.assertIs(service, get_service())

    def test_precise_crossing_has_osm_evidence_and_is_only_a_proposal(self):
        result = self.arcu
        fields = CandidateFields.model_validate(result["proposed_changes"])
        self.assertEqual("trecere", fields.precizie_loc)
        self.assertEqual((47.1665, 27.577216), (fields.lat, fields.lon))
        self.assertTrue(fields.in_iasi)
        self.assertIsNone(fields.location_evidence)
        self.assertNotIn("loc_text", result["proposed_changes"])
        self.assertIn("node/2186331539", result["report"]["referinte_osm"])
        self.assertEqual("trecere_unica_pe_strada", result["report"]["metoda"])
        self.assertEqual("ridicata", result["report"]["incredere"])
        self.assertTrue(result["needs_operator_confirmation"])
        self.assertFalse(result["persisted"])
        self.assertEqual("not_published", result["publication_status"])
        self.assertIn("de_verificat", result["report"])

    def test_street_and_vague_zone_points_remain_separate_from_event_coordinates(self):
        for text, precision in (("pe Bulevardul Socola", "strada"), ("trecerea din Nicolina", "vag"), ("intersecția din Copou", "vag")):
            with self.subTest(text=text):
                result = self.service.suggest(text, "observed")
                changes = result["proposed_changes"]
                self.assertEqual(precision, changes["precizie_loc"])
                self.assertIsNone(changes["lat"])
                self.assertIsNone(changes["lon"])
                self.assertIsNotNone(result["report"]["punct_orientativ"])
                self.assertTrue(any("orientativ" in value for value in result["warnings"]))
                CandidateFields.model_validate(changes)

    def test_outside_municipality_and_unknown_location_are_not_promoted(self):
        outside = self.service.suggest("în comuna Tomești, pe strada principală", "observed")
        self.assertFalse(outside["proposed_changes"]["in_iasi"])
        self.assertEqual("vag", outside["proposed_changes"]["precizie_loc"])
        self.assertIsNone(outside["proposed_changes"]["lat"])
        unknown = self.service.suggest("loc complet necunoscut fără nume", "observed")
        self.assertIsNone(unknown["proposed_changes"]["in_iasi"])
        self.assertIsNone(unknown["proposed_changes"]["lon"])
        self.assertTrue(unknown["report"]["de_verificat"])

    def test_unverified_known_node_is_reported_but_not_used(self):
        result = self.service.suggest("intersecția de la Podu Roș", "observed")
        self.assertIn("podu-ros", result["report"]["noduri_neverificate"])
        self.assertNotEqual("nod_cunoscut_verificat", result["report"]["metoda"])
        self.assertIsNone(result["proposed_changes"]["lat"])
        self.assertTrue(result["report"]["de_verificat"])

    def test_source_hashes_outputs_and_normalization_state_are_stable_and_read_only(self):
        from coordonate import normalizare
        saved = {name: deepcopy(getattr(normalizare, name)) for name in ("PREFIXE", "ALIAS_NUME", "ALIAS_REPERE")}
        with patch("socket.socket", side_effect=AssertionError("offline only")):
            first = self.service.suggest("trecerea de pe Strada Arcu", "observed")
            second = self.service.suggest("trecerea de pe Strada Arcu", "observed")
        self.assertEqual(first, second)
        self.assertEqual(self.before, first["provenance"]["input_hashes"])
        self.assertEqual(0, first["provenance"]["network_requests"])
        self.assertEqual("relation/1207838", first["provenance"]["boundary_osm"])
        self.assertNotIn("generated_at", first["provenance"])
        self.assertEqual(10, len(first["provenance"]["algorithm_hashes"]))
        self.assertEqual(saved, {name: getattr(normalizare, name) for name in saved})
        self.assertEqual(self.before, {name: hashlib.sha256((REFERENCES / name).read_bytes()).hexdigest() for name in FILES})
        first["provenance"]["input_hashes"].clear()
        self.assertEqual(4, len(self.service.suggest("trecerea de pe Strada Arcu", "observed")["provenance"]["input_hashes"]))

    def test_synthetic_mode_and_invalid_text_fail_before_any_reference_read(self):
        service = GeocodingService("missing-directory")
        with patch.object(Path, "read_bytes", side_effect=AssertionError("no IO")):
            error = self.assert_error(service.suggest, "trecerea de pe Strada Arcu", "synthetic")
            self.assertEqual((422, "synthetic_geocoding_unavailable"), (error.status, error.code))
            for mode, text in (("mixed", "Arcu"), ("observed", None), ("observed", " "), ("observed", "x" * 10_001)):
                self.assertEqual(422, self.assert_error(service.suggest, text, mode).status)

    def test_missing_corrupt_gzip_duplicate_keys_and_bad_aliases_fail_closed(self):
        self.assertEqual(503, self.assert_error(GeocodingService("missing-directory").suggest, "Arcu", "observed").status)
        directory = self.copy_inputs()
        index_path = directory / "osm/index_osm.json.gz"
        original = index_path.read_bytes()
        for raw in (b"not-gzip", gzip.compress(b'{"meta":{},"meta":{}}'), gzip.compress(b'{"v":NaN}')):
            index_path.write_bytes(raw)
            self.assertEqual(503, self.assert_error(GeocodingService(directory).suggest, "Arcu", "observed").status)
        index_path.write_bytes(original)
        (directory / "alias_nume.json").write_text('{"alias_nume":{},"repere":{"palas":5},"prefixe":{}}', encoding="utf-8")
        self.assertEqual(503, self.assert_error(GeocodingService(directory).suggest, "Arcu", "observed").status)

    def test_invalid_coordinates_and_missing_iasi_boundary_fail_closed(self):
        directory = self.copy_inputs()
        index_path = directory / "osm/index_osm.json.gz"
        original = index_path.read_bytes()
        data = json.loads(gzip.decompress(original))
        first_node = next(iter(data["noduri"]))
        data["noduri"][first_node] = [10 ** 400, 27.58]
        index_path.write_bytes(gzip.compress(json.dumps(data).encode()))
        self.assertEqual(503, self.assert_error(GeocodingService(directory).suggest, "Arcu", "observed").status)
        index_path.write_bytes(original)
        path = directory / "osm/unitati_admin.geojson"
        boundaries = json.loads(path.read_text(encoding="utf-8"))
        boundaries["features"] = [feature for feature in boundaries["features"] if feature["properties"]["osm"] != "relation/1207838"]
        path.write_text(json.dumps(boundaries), encoding="utf-8")
        self.assertEqual(503, self.assert_error(GeocodingService(directory).suggest, "Arcu", "observed").status)

    def test_changed_algorithm_requires_restart_instead_of_claiming_a_new_hash(self):
        from api import geocoding
        original = geocoding._read_files
        def changed(root, names):
            raw = original(root, names)
            if "rezolvare.py" in raw:
                raw["rezolvare.py"] += b"\n# source changed after module load\n"
            return raw
        with patch("api.geocoding._read_files", side_effect=changed):
            error = self.assert_error(self.service.suggest, "trecerea de pe Strada Arcu", "observed")
        self.assertEqual("geocoding_restart_required", error.code)


if __name__ == "__main__":
    unittest.main()
