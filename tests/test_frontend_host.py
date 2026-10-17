"""The local UI must share API origin without weakening review access controls."""

from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from api.main import create_app


class FrontendHostTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.app = create_app(frontend_directory=self.directory)
        self.client = TestClient(self.app, base_url="http://127.0.0.1", client=("127.0.0.1", 53002))
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def test_missing_or_wrong_base_build_is_503_without_affecting_backend(self):
        self.assertEqual("frontend_build_unavailable", self.client.get("/ui/").json()["detail"]["code"])
        (self.directory / "index.html").write_text('<base href="/"><h1>wrong build</h1>', encoding="utf-8")
        self.assertEqual(503, self.client.get("/ui/").status_code)
        self.assertEqual(200, self.client.get("/health").status_code)
        self.assertEqual(200, self.client.get("/docs").status_code)

    def test_build_and_assets_are_served_only_below_ui_and_guarded_locally(self):
        (self.directory / "index.html").write_text('<base href="/ui/"><h1>UI</h1>', encoding="utf-8")
        (self.directory / "main.js").write_text('document.title="test";', encoding="utf-8")
        self.assertIn("<h1>UI</h1>", self.client.get("/ui/").text)
        self.assertEqual(200, self.client.get("/ui/main.js").status_code)
        self.assertEqual(404, self.client.get("/main.js").status_code)
        self.assertEqual(404, self.client.get("/ui/%2e%2e/api/main.py").status_code)
        self.assertEqual(403, self.client.get("/ui/", headers={"Origin":"https://example.org"}).status_code)
        with TestClient(self.app, base_url="http://127.0.0.1", client=("192.0.2.1", 53001)) as remote:
            self.assertEqual(403, remote.get("/ui/").status_code)


if __name__ == "__main__":
    unittest.main()
