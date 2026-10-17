import csv
import tempfile
import unittest
from pathlib import Path

from scraping.procesare_articole_ai import main, read_articles, exporta_csv_curatat


class ProcesareArticoleAiTests(unittest.TestCase):
    def test_clean_csv_preserves_rows_urls_and_other_columns(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            source, target = Path(tmp) / "raw.csv", Path(tmp) / "clean.csv"
            rows = [{"url": "https://example.test/1", "text": "Text sintetic.\nLasă un răspuns Anulează răspunsul", "extra": "a,b"},
                    {"url": "https://example.test/1", "text": "Alt text sintetic.", "extra": "neschimbat"}]
            with source.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["url", "text", "extra"])
                writer.writeheader()
                writer.writerows(rows)
            original_bytes = source.read_bytes()
            self.assertEqual(exporta_csv_curatat(source, target), {"randuri_csv": 2, "texte_curatate": 1})
            with target.open(encoding="utf-8-sig", newline="") as handle:
                actual = list(csv.DictReader(handle))
            self.assertEqual(len(actual), 2)
            self.assertEqual(actual[0], {**rows[0], "text": "Text sintetic."})
            self.assertEqual(actual[1], rows[1])
            self.assertEqual(source.read_bytes(), original_bytes)
            with self.assertRaises(ValueError):
                exporta_csv_curatat(source, source)
    def test_handoff_removes_only_terminal_comment_ui(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            path = Path(tmp) / "input.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["url", "titlu", "text"])
                writer.writeheader()
                writer.writerow({"url": "https://example.test", "titlu": "Test sintetic",
                                 "text": "Corpul sintetic.\nLasă un răspuns Anulează răspunsul"})
            audit = {}
            self.assertEqual(read_articles(path, audit=audit)[0]["text"], "Corpul sintetic.")
            self.assertEqual(audit["randuri_csv"], 1)
            self.assertEqual(audit["texte_curatate"], 1)
            self.assertEqual(audit["urluri_unice"], 1)
            self.assertFalse(audit["filtrare_relevanta"])

    def test_csv_contract_preserves_text_and_unknown_retrieval_time(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            path = Path(tmp) / "input.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["url", "titlu", "text", "sursa", "data_publicarii"])
                writer.writeheader()
                writer.writerow(dict(url="https://example.test/synthetic", titlu="SINTETIC",
                                     text="Text sintetic.\nAl doilea paragraf.", sursa="SINTETIC",
                                     data_publicarii="2026-03-10"))
            articles = read_articles(path)
            self.assertEqual(articles[0]["text"], "Text sintetic.\nAl doilea paragraf.")
            self.assertEqual(articles[0]["colectat_la"], "")
            self.assertEqual(set(articles[0]), {"article_id", "sursa", "url", "titlu", "text", "publicat_la", "colectat_la"})
            self.assertEqual(main(["--intrare", str(path), "--director", str(Path(tmp) / "out"), "--pipeline", "rules"]), 0)
            self.assertTrue((Path(tmp) / "out" / "toate.csv").exists())
            with (Path(tmp) / "out" / "toate.csv").open(encoding="utf-8-sig", newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["verificat"], "False")
            self.assertEqual(row["in_iasi"], "")


if __name__ == "__main__":
    unittest.main()
