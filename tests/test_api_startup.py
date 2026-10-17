"""Check local HTTP startup and its independence from AI keys and datasets."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app, create_app


class ApiStartupTests(unittest.TestCase):
    def test_health_and_documentation_are_accessible(self):
        with patch("ai.router.ExtractionService", side_effect=AssertionError("startup must not require AI")), TestClient(app) as client:
            response = client.get("/health")
            self.assertEqual(200, response.status_code)
            self.assertEqual({"status": "ok", "service": "safeiasi-api"}, response.json())
            self.assertEqual(200, client.get("/docs").status_code)
            schema = client.get("/openapi.json")
            self.assertEqual(200, schema.status_code)
            self.assertIn("/health", schema.json()["paths"])
            self.assertIn("/api/v1/ai/extract", schema.json()["paths"])
            self.assertIn("/api/v1/ai/replays/{article_id}", schema.json()["paths"])
            home = client.get("/", follow_redirects=False)
            self.assertEqual(307, home.status_code)
            self.assertEqual("/docs", home.headers["location"])

    def test_legacy_entry_point_and_repeated_registration_keep_one_operation(self):
        from ai.app import app as legacy_app, create_app as legacy_factory, register_ai

        self.assertIs(app, legacy_app)
        self.assertIs(create_app, legacy_factory)
        application = create_app()
        original_schema = application.openapi()
        route_count = len(application.routes)
        register_ai(application)
        register_ai(application)
        self.assertEqual(route_count, len(application.routes))
        self.assertEqual(original_schema, application.openapi())

    def test_entry_points_import_in_either_order_without_provider_or_route_duplicates(self):
        for first, second in (("api.main", "ai.app"), ("ai.app", "api.main")):
            with self.subTest(first=first):
                script = (
                    "import importlib; from unittest.mock import patch; "
                    "\nwith patch('urllib.request.urlopen', side_effect=AssertionError('unexpected network')):\n"
                    f" first = importlib.import_module({first!r})\n"
                    " route_count = len(first.app.routes)\n"
                    f" second = importlib.import_module({second!r})\n"
                    " assert first.app is second.app\n"
                    " assert route_count == len(second.app.routes)\n"
                    " assert 'post' in first.app.openapi()['paths']['/api/v1/ai/extract']\n"
                )
                result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=15)
                self.assertEqual(0, result.returncode, result.stderr)

    def test_startup_from_empty_directory_without_api_credentials(self):
        repository = Path(__file__).resolve().parents[1]
        # Use a minimal child environment, excluding AI keys and data settings.
        environment = {
            key: os.environ[key] for key in ("SYSTEMROOT", "TEMP", "TMP") if key in os.environ
        }
        environment.update(PYTHONPATH=str(repository), PYTHONDONTWRITEBYTECODE="1")
        script = (
            "from fastapi.testclient import TestClient; "
            "from api.main import app; "
            "\nwith TestClient(app) as client:\n"
            " response = client.get('/health')\n"
            " assert response.status_code == 200, response.text\n"
            " assert response.json()['status'] == 'ok'\n"
            " assert client.get('/api/v1/manifest').status_code == 503\n"
            " assert '/api/v1/ai/extract' in client.get('/openapi.json').json()['paths']\n"
            " replay = client.get('/api/v1/ai/replays/syn-003')\n"
            " assert replay.status_code == 200, replay.text\n"
            " assert replay.json()['processing_mode'] == 'replay'\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            environment["SAFEIASI_SNAPSHOT_DIR"] = directory
            result = subprocess.run(
                [sys.executable, "-c", script], cwd=directory, env=environment,
                capture_output=True, text=True, timeout=30,
            )
        self.assertEqual(0, result.returncode, result.stderr)


if __name__ == "__main__":
    unittest.main()
