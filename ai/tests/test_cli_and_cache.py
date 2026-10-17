import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai.cli import main
from ai.engine import Ollama, run

AI = Path(__file__).resolve().parents[1]
REPO = AI.parent
TEMP = AI / "work" / "tests"
TEMP.mkdir(parents=True, exist_ok=True)


class CliAndCacheTests(unittest.TestCase):
    def test_single_hybrid_selection_computes_its_dependencies(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as directory, contextlib.redirect_stdout(io.StringIO()):
            with patch("ai.engine.urllib.request.urlopen", side_effect=AssertionError("unexpected network")):
                status = main(["--articles", str(AI / "benchmarks/source_articles.json"),
                               "--out", directory, "--pipelines", "hybrid",
                               "--cache", str(AI / "benchmarks/cache"),
                               "--base-url", "http://127.0.0.1:11435"])
            self.assertEqual(0, status)
            result = json.loads((Path(directory) / "hybrid.json").read_text(encoding="utf-8"))
            self.assertEqual(4, len(result["accidents"]))
            self.assertEqual(1, len(result["duplicate_review_queue"]))

    def test_shared_false_data_cannot_be_an_output_or_cache_directory(self):
        with contextlib.redirect_stderr(io.StringIO()):
            for option in ("--out", "--cache"):
                with self.assertRaises(SystemExit) as caught:
                    main([option, str(REPO / "false_data"), "--pipelines", "rules"])
                self.assertEqual(2, caught.exception.code)

    def test_module_cli_runs_from_repository_root(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as directory:
            completed = subprocess.run([sys.executable, "-m", "ai", "--pipelines", "rules", "--out", directory],
                                       cwd=REPO, capture_output=True, text=True, timeout=15)
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertTrue((Path(directory) / "rules/accidents.json").exists())

    def test_backend_plus_ai_starts_without_credentials_from_empty_cwd(self):
        environment = {key: os.environ[key] for key in ("SYSTEMROOT", "TEMP", "TMP") if key in os.environ}
        environment.update(PYTHONPATH=str(REPO), PYTHONDONTWRITEBYTECODE="1")
        script = ("from fastapi.testclient import TestClient; from ai.app import app; "
                  "c=TestClient(app); assert c.get('/health').json()=={'status':'ok','service':'safeiasi-api'}; "
                  "r=c.get('/api/v1/ai/replays/syn-003'); assert r.status_code==200; "
                  "assert r.json()['processing_mode']=='replay'")
        with tempfile.TemporaryDirectory(dir=TEMP) as directory:
            completed = subprocess.run([sys.executable, "-c", script], cwd=directory, env=environment,
                                       capture_output=True, text=True, timeout=20)
        self.assertEqual(0, completed.returncode, completed.stderr)

    def test_frozen_model_predictions_reproduce_without_any_network(self):
        articles = json.loads((AI / "benchmarks/source_articles.json").read_text(encoding="utf-8"))
        with patch("ai.engine.urllib.request.urlopen", side_effect=AssertionError("unexpected network")), contextlib.redirect_stdout(io.StringIO()):
            for model, folder in (("qwen2.5:1.5b", "results_1p5"), ("qwen2.5:3b", "results_3b")):
                client = Ollama(model, "http://127.0.0.1:11435", AI / "benchmarks/cache")
                for pipeline in ("direct", "evidence"):
                    expected = json.loads((AI / "benchmarks" / folder / (pipeline + ".json")).read_text(encoding="utf-8"))
                    actual = run(articles, pipeline, client)
                    self.assertEqual([r["extracted"] for r in expected["rows"]], [r["extracted"] for r in actual["rows"]])
                    self.assertTrue(all(r["trace"]["cache_hit"] for r in actual["rows"]))
