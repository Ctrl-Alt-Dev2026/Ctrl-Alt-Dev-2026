import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from ai.gemini_pipeline import build_prompt, parse_response, run_gemini_csv
from ai.press_pipeline import _article, _csv, _read
from ai.router import GeminiCsvRequest, extract


class GeminiCsvTests(unittest.TestCase):
    def test_rejects_missing_duplicate_and_fabricated_ids(self):
        article = _article({"url": "https://example.test/1", "titlu": "Test", "text": "Text."}, 1)
        item = {"article_id": article["article_id"], "tip_stire": "alt_subiect", "stare": "respins", "motiv": "Alt subiect",
                "citate": ["Text."], "extragere": None}
        for items in ([], [item, item], [{**item, "article_id": "inventat"}]):
            with self.assertRaises(ValueError):
                parse_response(json.dumps({"rezultate": items}), [article])

    def test_fake_quote_becomes_uncertain(self):
        article = _article({"url": "https://example.test/1", "titlu": "Test", "text": "Text."}, 1)
        item = {"article_id": article["article_id"], "tip_stire": "accident_actual", "stare": "valid", "motiv": "Test",
                "citate": ["inventat"], "extragere": None}
        result = parse_response(json.dumps({"rezultate": [item]}), [article])
        self.assertEqual(result[article["article_id"]]["stare"], "neclar")

    def test_full_flow_and_resume_reuse_real_response_contract(self):
        rows = [{"url": "https://example.test/1", "titlu": "Pieton", "text": "Un pieton traversa regulamentar și a fost lovit de un autoturism."},
                {"url": "https://example.test/2", "titlu": "Control", "text": "Polițiștii au organizat controale."}]
        articles = [_article(row, i) for i, row in enumerate(rows, 1)]
        extraction = {"is_event": True, "evidence_ids": {key: 0 if key in ("event", "participants") else None
                      for key in ("event", "date", "time", "location", "participants", "severity", "cause", "night")},
                      "data_eveniment": None, "ora": None, "loc_text": None,
                      "participanti": ["pieton", "autoturism"], "gravitate": "necunoscut",
                      "cauza_raportata": None, "noapte": None}
        extraction["evidence_ids"]["night"] = False
        response = json.dumps({"rezultate": [{"article_id": article["article_id"],
            "tip_stire": "accident_actual" if i == 0 else "alt_subiect",
            "stare": "valid" if i == 0 else "respins", "motiv": "Test", "citate": [article["text"]],
            "extragere": extraction if i == 0 else None} for i, article in enumerate(articles)]})
        client = Mock()
        client.model = "gemini-test"
        client.ask.return_value = response
        factory = Mock()
        factory.return_value.__enter__ = Mock(return_value=client)
        factory.return_value.__exit__ = Mock(return_value=False)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.csv"
            output = Path(directory) / "out"
            _csv(source, list(rows[0]), rows)
            report = run_gemini_csv(source, output, client_factory=factory, cache_only=False)
            self.assertEqual(report["status"], "completed")
            self.assertEqual(report["valid"], 1)
            self.assertEqual(report["rejected"], 1)
            self.assertEqual(len(report["articole_valide"]), 1)
            item = report["articole_valide"][0]
            self.assertEqual(item["url"], rows[0]["url"])
            self.assertEqual(item["text"], rows[0]["text"])
            self.assertEqual(item["clasificare"]["stare"], "valid")
            self.assertEqual(len(item["extragere"]["candidates"]), 1)
            self.assertFalse(item["extragere"]["candidates"][0]["verificat"])
            self.assertTrue(any("evidence_ids.night" in issue for issue in item["clasificare"]["issues"]))
            self.assertIsNone(item["extragere"]["candidates"][0]["noapte"])
            _, valid = _read(output / "articole_valide.csv")
            self.assertEqual(valid[0]["text"], rows[0]["text"])
            self.assertEqual(len(json.loads((output / "extractii.json").read_text(encoding="utf-8"))), 1)
            for cached in (output / "responses").glob("*.json"):
                if not cached.name.endswith(".raw.json"):
                    cached.unlink()
            report = run_gemini_csv(source, output, client_factory=factory, cache_only=False)
            self.assertEqual(report["status"], "completed")
        client.ask.assert_called_once()

    def test_bad_extraction_type_marks_only_that_article_uncertain(self):
        article = _article({"url": "https://example.test/bad", "titlu": "Pieton lovit",
                            "text": "Un pieton a fost lovit de un autoturism."}, 1)
        item = {"article_id": article["article_id"], "tip_stire": "accident_actual", "stare": "valid",
                "motiv": "Accident", "citate": [article["text"]], "extragere": "not an object"}
        result = parse_response(json.dumps({"rezultate": [item]}), [article])[article["article_id"]]
        self.assertEqual(result["stare"], "neclar")
        self.assertIsNone(result["extragere"])
        self.assertTrue(result["issues"])

    def test_judicial_followup_is_never_accepted_even_if_model_says_valid(self):
        text = "Judecătorii au decis arestarea după coliziunea dintre două autoturisme."
        article = _article({"url": "https://example.test/cavali", "titlu": "Roberto Cavali a fost arestat după accident", "text": text}, 1)
        item = {"article_id": article["article_id"], "tip_stire": "urmare_judiciara", "stare": "valid",
                "motiv": "Accident cu răniți", "citate": [text], "extragere": None}
        result = parse_response(json.dumps({"rezultate": [item]}), [article])[article["article_id"]]
        self.assertEqual(result["stare"], "respins")
        self.assertIsNone(result["extragere"])

    def test_car_collision_cannot_pass_with_invented_pedestrian(self):
        text = "Două autoturisme au fost proiectate pe trotuarul pietonal și au lovit un stâlp; pasagerii au fost transportați la spital."
        article = _article({"url": "https://example.test/collision", "titlu": "Accident", "text": text}, 1)
        extraction = {"is_event": True, "evidence_ids": {key: 0 if key in ("event", "participants") else None
            for key in ("event", "date", "time", "location", "participants", "severity", "cause", "night")},
            "data_eveniment": None, "ora": None, "loc_text": None, "participanti": ["pieton", "autoturism"],
            "gravitate": "necunoscut", "cauza_raportata": None, "noapte": None}
        item = {"article_id": article["article_id"], "tip_stire": "accident_actual", "stare": "valid",
                "motiv": "Accident", "citate": [text], "extragere": extraction}
        result = parse_response(json.dumps({"rezultate": [item]}), [article])[article["article_id"]]
        self.assertEqual(result["stare"], "neclar")
        self.assertIsNone(result["extragere"])

    def test_prompt_uses_shared_schema_and_keeps_full_sentences(self):
        articles = [_article({"url": "https://example.test/" + str(i), "titlu": "Test",
                              "text": "Prima frază. A doua frază."}, i) for i in range(4)]
        prompt = build_prompt(articles)
        self.assertEqual(prompt.count('"additionalProperties":false'), 2)
        self.assertEqual(prompt.count('"fraze":["Prima frază.","A doua frază."]'), 4)
        self.assertIn("deschiderea unui dosar penal", prompt)

    def test_route_does_not_use_ollama(self):
        service = Mock()
        result = {"errors": [], "status": "completed", "articole_valide": [{"article_id": "test", "extragere": {"candidates": []}}]}
        service.extract_gemini_csv.return_value = result
        response = extract(GeminiCsvRequest(mode="gemini_csv", limit=2), service)
        service.extract_gemini_csv.assert_called_once_with(limit=2, cache_only=True)
        service.extract.assert_not_called()
        self.assertEqual(response.headers["x-ai-provider"], "gemini")
        self.assertEqual(response.media_type, "application/json")
        self.assertEqual(json.loads(response.body), result)

    def test_failure_returns_json_not_a_stale_export(self):
        service = Mock()
        result = {"status": "interrupted", "errors": ["quota"], "articole_valide": []}
        service.extract_gemini_csv.return_value = result
        response = extract(GeminiCsvRequest(mode="gemini_csv"), service)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(json.loads(response.body), result)
