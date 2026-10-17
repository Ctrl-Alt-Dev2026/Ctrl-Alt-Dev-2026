import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from ai.gemini_pipeline import SHARED_CACHE, run_gemini_csv
from ai.press_pipeline import DEFAULT_CSV, _csv
from ai.router import GeminiCsvRequest, extract


class CacheOnlyTests(unittest.TestCase):
    def test_shared_94_articles_work_without_key_or_network(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch("ai.gemini_client.GeminiClient.__init__", side_effect=AssertionError("must not read key")), \
             patch("urllib.request.urlopen", side_effect=AssertionError("must not call network")):
            report = run_gemini_csv(output=directory, cache_only=True)
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["processed"], 94)
        self.assertEqual(report["cache_hits"], 24)
        self.assertEqual(report["api_calls"], 0)
        self.assertEqual(len(report["articole_valide"]), report["valid"])

    def test_missing_cache_never_constructs_client_or_calls_network(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch("urllib.request.urlopen", side_effect=AssertionError("must not call network")):
            root = Path(directory)
            source = root / "source.csv"
            _csv(source, ["url", "titlu", "text"], [{"url": "https://example.test/new", "titlu": "New", "text": "New text."}])
            client = Mock(side_effect=AssertionError("must not construct client"))
            report = run_gemini_csv(source, root / "out", cache_only=True, shared_cache=root / "empty", client_factory=client)
            client.assert_not_called()
        self.assertEqual(report["status"], "cache_miss")
        self.assertEqual(report["api_calls"], 0)
        self.assertFalse(report["complete_input"])

    def test_manifest_matches_source_and_response_files(self):
        manifest = json.loads((SHARED_CACHE / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(hashlib.sha256(DEFAULT_CSV.read_bytes()).hexdigest(), manifest["source_sha256"])
        self.assertEqual(manifest["batch_count"], len(manifest["responses"]))
        for entry in manifest["responses"]:
            data = (SHARED_CACHE / "responses" / entry["file"]).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), entry["sha256"])
            self.assertNotIn(b"AIza", data)

    def test_route_returns_conflict_for_cache_miss_and_live_requires_opt_in(self):
        service = Mock()
        service.extract_gemini_csv.return_value = {"status": "cache_miss", "errors": ["missing"], "articole_valide": []}
        response = extract(GeminiCsvRequest(mode="gemini_csv"), service)
        self.assertEqual(response.status_code, 409)
        service.extract_gemini_csv.assert_called_once_with(limit=None, cache_only=True)
        service.reset_mock()
        extract(GeminiCsvRequest(mode="gemini_csv", cache_only=False), service)
        service.extract_gemini_csv.assert_called_once_with(limit=None, cache_only=False)
