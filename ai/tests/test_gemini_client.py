import io
import json
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from ai.gemini_client import GeminiClient
from ai.router import GeminiTestRequest, extract


class GeminiClientTests(unittest.TestCase):
    def test_header_auth_rest_json_and_no_key_in_url(self):
        response = Mock()
        response.__enter__ = Mock(return_value=io.StringIO(json.dumps({"candidates": [{
            "finishReason": "STOP", "content": {"parts": [{"text": '{"ok":true}'}]}}]})))
        response.__exit__ = Mock(return_value=False)
        with patch("ai.gemini_client.urllib.request.urlopen", return_value=response) as send:
            text = GeminiClient(api_key="not-a-real-secret").ask("Test")
        self.assertEqual(json.loads(text), {"ok": True})
        request = send.call_args.args[0]
        self.assertNotIn("not-a-real-secret", request.full_url)
        self.assertEqual(request.get_header("X-goog-api-key"), "not-a-real-secret")
        self.assertEqual(json.loads(request.data)["generationConfig"]["responseMimeType"], "application/json")

    def test_quota_stops_once_and_redacts_provider_error(self):
        error = HTTPError("https://example.test", 429, "not-a-real-secret", {}, io.BytesIO(b"not-a-real-secret"))
        with patch("ai.gemini_client.urllib.request.urlopen", side_effect=error) as send:
            with self.assertRaises(RuntimeError) as caught:
                GeminiClient(api_key="not-a-real-secret").ask("Test")
        self.assertNotIn("not-a-real-secret", str(caught.exception))
        self.assertIn("429", str(caught.exception))
        send.assert_called_once()

    def test_test_route_calls_only_connection_test(self):
        service = Mock()
        service.test_gemini.return_value = {"ok": True}
        self.assertEqual(extract(GeminiTestRequest(mode="gemini_test"), service), {"ok": True})
        service.extract.assert_not_called()

    def test_provider_message_is_reported_without_exposing_key(self):
        body = json.dumps({"error": {"message": "Model overloaded; key not-a-real-secret"}}).encode()
        error = HTTPError("https://example.test", 503, "Unavailable", {}, io.BytesIO(body))
        with patch("ai.gemini_client.urllib.request.urlopen", side_effect=error):
            with self.assertRaises(RuntimeError) as caught:
                GeminiClient(api_key="not-a-real-secret").ask("Test")
        self.assertIn("Model overloaded", str(caught.exception))
        self.assertNotIn("not-a-real-secret", str(caught.exception))

    def test_missing_key_fails_before_network(self):
        with patch("ai.gemini_client.CONFIG") as path, patch.dict("os.environ", {}, clear=True), \
             patch("ai.gemini_client.urllib.request.urlopen") as send:
            path.exists.return_value = False
            with self.assertRaises(ValueError):
                GeminiClient()
        send.assert_not_called()
