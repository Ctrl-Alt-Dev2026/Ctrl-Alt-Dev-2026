import copy
import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from ai import ExtractionConfig, ExtractionService, ExtractionUnavailable, extract_article

AI = Path(__file__).resolve().parents[1]
ARTICLES = json.loads((AI / "benchmarks/source_articles.json").read_text(encoding="utf-8"))


class ServiceTests(unittest.TestCase):
    def test_backend_function_returns_pending_v2_candidates(self):
        candidates = extract_article(ARTICLES[0], pipeline="rules")
        self.assertEqual(1, len(candidates))
        candidate = candidates[0]
        self.assertEqual(["syn-001"], candidate["article_ids"])
        self.assertEqual("2025-03-12", candidate["data_eveniment"])
        self.assertEqual("pending", candidate["review_status"])
        self.assertFalse(candidate["verificat"])
        for key in ("lat", "lon", "in_iasi", "precizie_loc"):
            self.assertIsNone(candidate[key])
        self.assertEqual("rules", candidate["extraction_runs"][0]["model"])

    def test_source_dictionaries_are_not_mutated(self):
        article = copy.deepcopy(ARTICLES[0])
        before = copy.deepcopy(article)
        ExtractionService().extract(article, "rules")
        self.assertEqual(before, article)

    def test_all_available_source_fields_match_annotations_with_rules(self):
        from ai.engine import FIELDS
        labels = json.loads((AI / "benchmarks/repository_annotations.json").read_text(encoding="utf-8"))["article_annotations"]
        for article, label in zip(ARTICLES, labels):
            candidate = extract_article(article, pipeline="rules")[0]
            for field in FIELDS:
                self.assertEqual(label[field], candidate[field], (article["article_id"], field))

    def test_coordinate_and_approval_injection_is_rejected(self):
        article = {**ARTICLES[0], "verificat": True, "lat": 47.0}
        with self.assertRaises(ValueError):
            extract_article(article, pipeline="rules")

    def test_empty_text_is_rejected(self):
        with self.assertRaises(ValueError):
            extract_article({**ARTICLES[0], "text": " "}, pipeline="rules")

    def test_hybrid_provider_failure_is_explicit_and_retains_pending_fallback(self):
        client = Mock()
        client.extract.side_effect = RuntimeError("provider offline")
        result = ExtractionService(client=client).extract(ARTICLES[0], "hybrid")
        self.assertTrue(result["errors"])
        self.assertEqual("rules_fallback", result["processing_mode"])
        self.assertEqual("pending", result["candidates"][0]["review_status"])
        self.assertIn("ai_unavailable_requires_review", result["candidates"][0]["issues"])

    def test_public_function_does_not_hide_provider_failure_as_irrelevance(self):
        client = Mock()
        client.extract.side_effect = RuntimeError("provider offline")
        with patch("ai.service.Ollama", return_value=client):
            with self.assertRaises(ExtractionUnavailable) as caught:
                extract_article(ARTICLES[0])
        self.assertEqual("rules_fallback", caught.exception.result["processing_mode"])

    def test_pure_ai_failure_has_no_invented_candidate(self):
        client = Mock()
        client.extract.side_effect = RuntimeError("provider offline")
        result = ExtractionService(client=client).extract(ARTICLES[0], "evidence")
        self.assertEqual([], result["candidates"])
        self.assertTrue(result["errors"])

    def test_irrelevant_source_is_distinct_from_provider_failure(self):
        article = {**ARTICLES[0], "text": "Nu a fost implicat niciun pieton. O tamponare între autoturisme."}
        result = ExtractionService().extract(article, "rules")
        self.assertEqual([], result["candidates"])
        self.assertEqual([], result["errors"])

    def test_agreement_and_hybrid_work_offline_from_frozen_cache(self):
        config = ExtractionConfig(base_url="http://127.0.0.1:11435", cache_dir=AI / "benchmarks/cache")
        with patch("ai.engine.urllib.request.urlopen", side_effect=AssertionError("unexpected network call")):
            for pipeline in ("agreement", "hybrid"):
                result = ExtractionService(config).extract(ARTICLES[0], pipeline)
                self.assertEqual("cache", result["processing_mode"])
                self.assertEqual([], result["errors"])

    def test_replay_remains_synthetic_unapproved_and_labeled(self):
        result = ExtractionService().replay("syn-003")
        self.assertEqual("replay", result["processing_mode"])
        self.assertEqual("synthetic", result["data_mode"])
        self.assertIn("SYNTHETIC REPLAY", result["label"])
        self.assertFalse(result["candidates"][0]["verificat"])

    def test_no_file_protocol_provider(self):
        with self.assertRaises(ValueError):
            ExtractionConfig(base_url="file:///etc/passwd")
