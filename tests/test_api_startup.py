"""Check local HTTP startup and its independence from AI keys and datasets."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from fastapi.testclient import TestClient

from api.main import app


class ApiStartupTests(unittest.TestCase):
    def test_health_and_documentation_are_accessible(self):
        with TestClient(app) as client:
            response = client.get("/health")
            self.assertEqual(200, response.status_code)
            self.assertEqual({"status": "ok", "service": "safeiasi-api"}, response.json())
            self.assertEqual(200, client.get("/docs").status_code)
            schema = client.get("/openapi.json")
            self.assertEqual(200, schema.status_code)
            self.assertIn("/health", schema.json()["paths"])
            home = client.get("/", follow_redirects=False)
            self.assertEqual(307, home.status_code)
            self.assertEqual("/docs", home.headers["location"])

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
