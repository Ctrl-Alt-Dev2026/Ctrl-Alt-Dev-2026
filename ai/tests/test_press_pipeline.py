import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from ai.cli import main
from ai.press_pipeline import _ground
from ai.service import ExtractionConfig, ExtractionService


class PressPipelineTests(unittest.TestCase):
    def test_filter_then_read_valid_csv_then_extract_only_selected(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parents[1]) as tmp:
            root = Path(tmp)
            source = root / "clean.csv"
            rows = [
                {"url": "https://example.test/1", "titlu": "SINTETIC accident",
                 "text": "Un pieton a fost lovit de un autoturism.\nText sintetic.", "sursa": "SINTETIC"},
                {"url": "https://example.test/2", "titlu": "SINTETIC control",
                 "text": "Controale ale poliției. Text sintetic.", "sursa": "SINTETIC"},
                {"url": "https://example.test/3", "titlu": "SINTETIC neclar",
                 "text": "Informații insuficiente. Text sintetic.", "sursa": "SINTETIC"},
            ]
            with source.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            original_bytes = source.read_bytes()
            service = ExtractionService(ExtractionConfig(cache_dir=root / "cache"), client=Mock())
            states = iter(["valid", "respins", "neclar"])
            with patch.object(service, "extract", wraps=service.extract) as extract_call:
                def classify(client, article):
                    self.assertEqual(extract_call.call_count, 0, "Filtering must finish before extraction.")
                    return {"stare": next(states), "motiv": "Exemplu simulat", "citate": [article["text"]], "issues": []}
                with patch("ai.press_pipeline.classify_article", side_effect=classify) as filter_call:
                    result = service.extract_clean_csv(source, root / "output", pipeline="rules")
                self.assertEqual(filter_call.call_count, 3)
                self.assertEqual(extract_call.call_count, 1)
                self.assertEqual(extract_call.call_args.args[0]["text"], rows[0]["text"])
            self.assertEqual((result["valid"], result["rejected"], result["uncertain"], result["extracted"]), (1, 1, 1, 1))
            self.assertEqual(source.read_bytes(), original_bytes)
            for name, count in [("clasificare.csv", 3), ("articole_valide.csv", 1),
                                ("articole_respinse.csv", 1), ("articole_neclare.csv", 1), ("extractii.csv", 1)]:
                with (root / "output" / name).open(encoding="utf-8-sig", newline="") as handle:
                    exported = list(csv.DictReader(handle))
                self.assertEqual(len(exported), count)
            saved = json.loads((root / "output/extractii.json").read_text(encoding="utf-8"))
            self.assertEqual(saved[0]["review_status"], "pending")

    def test_default_service_call_delegates_to_clean_csv_flow(self):
        service = ExtractionService(client=Mock())
        with patch.object(service, "extract_clean_csv", return_value={"status": "completed"}) as flow:
            self.assertEqual(service.extract(), {"status": "completed"})
            flow.assert_called_once_with(pipeline="hybrid")

    def test_normal_module_entry_automatically_selects_csv_flow(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parents[1]) as tmp:
            fake = Mock()
            fake.extract_clean_csv.return_value = {
                "valid": 1, "rejected": 1, "uncertain": 0, "extracted": 1,
                "errors": [], "status": "completed"}
            with patch("ai.cli.ExtractionService", return_value=fake):
                self.assertEqual(main(["--out", tmp]), 0)
            fake.extract_clean_csv.assert_called_once_with(source=None, output=Path(tmp), pipeline="hybrid", limit=None)

    def test_fabricated_quotes_cannot_reject_or_validate(self):
        article = {"titlu": "SINTETIC", "text": "Text sintetic."}
        for state in ("valid", "respins"):
            result = _ground({"stare": state, "motiv": "Test", "citate": ["Citat inventat."]}, article)
            self.assertEqual(result["stare"], "neclar")

    def test_no_argument_module_run_uses_press_output_and_default_csv(self):
        from ai.service import AI_DIR
        fake = Mock()
        fake.extract_clean_csv.return_value = {
            "valid": 0, "rejected": 0, "uncertain": 0, "extracted": 0,
            "errors": [], "status": "completed"}
        with patch("ai.cli.ExtractionService", return_value=fake):
            self.assertEqual(main([]), 0)
        fake.extract_clean_csv.assert_called_once_with(
            source=None, output=AI_DIR / "work" / "presa", pipeline="hybrid", limit=None)

    def test_filter_failure_does_not_feed_partial_batch_to_extraction(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parents[1]) as tmp:
            root = Path(tmp)
            source = root / "clean.csv"
            source.write_text("url,titlu,text\nhttps://example.test,Test,Text sintetic\nhttps://example.test/2,Test2,Text sintetic\n", encoding="utf-8")
            service = ExtractionService(ExtractionConfig(cache_dir=root / "cache"), client=Mock())
            with patch("ai.press_pipeline.classify_article", side_effect=RuntimeError("model offline")), \
                 patch.object(service, "extract") as extract_call:
                result = service.extract_clean_csv(source, root / "out")
            self.assertEqual(result["status"], "interrupted_filtering")
            self.assertEqual(result["filtered"], 1)
            extract_call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
