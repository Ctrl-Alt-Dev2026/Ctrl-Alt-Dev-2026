"""Gemini Developer API REST client; no extra dependencies or billing changes."""
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request

CONFIG = Path(__file__).resolve().parent / "gemini.local.json"
DEFAULT_MODEL = "gemini-3.5-flash-lite"


class GeminiClient:
    def __init__(self, api_key=None, model=None, timeout=90):
        settings = json.loads(CONFIG.read_text(encoding="utf-8-sig")) if CONFIG.exists() else {}
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or settings.get("api_key", "")
        self.model = model or os.getenv("SAFEIASI_GEMINI_MODEL") or settings.get("model", DEFAULT_MODEL)
        self.timeout = timeout
        if not self.api_key or self.api_key == "PUNE_CHEIA_AICI":
            raise ValueError("Completează api_key în ai/gemini.local.json sau setează GEMINI_API_KEY pe server.")
        if not re.fullmatch(r"gemini-[a-z0-9.-]+", self.model):
            raise ValueError("Nume de model Gemini invalid.")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def ask(self, prompt, *, json_output=True):
        config = {"temperature": 0, "maxOutputTokens": 8192}
        if json_output:
            config["responseMimeType"] = "application/json"
        request = urllib.request.Request(
            "https://generativelanguage.googleapis.com/v1beta/models/" + self.model + ":generateContent",
            data=json.dumps({"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                             "generationConfig": config}, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                obj = json.load(response)
        except urllib.error.HTTPError as exc:
            # Do not log request headers, key, provider body or URLs containing credentials.
            messages = {400: "Cerere invalidă sau cheie API invalidă.",
                        401: "Cheie API neacceptată.", 403: "Cheia/proiectul nu are acces la Gemini API.",
                        404: "Modelul configurat nu este disponibil pentru această cheie.",
                        429: "Cotă Gemini epuizată sau limită de ritm. Verifică AI Studio; nu activa billing pentru acest test."}
            detail = ""
            try:
                error = json.loads(exc.read(16384)).get("error", {})
                message = error.get("message", "")
                if isinstance(message, str):
                    message = message.replace(self.api_key, "[REDACTAT]")
                    message = re.sub(r"AIza[\w-]+", "[REDACTAT]", message)
                    detail = " Google: " + message[:500] if message else ""
            except (ValueError, TypeError, AttributeError):
                pass
            raise RuntimeError(f"Gemini HTTP {exc.code}: " + messages.get(exc.code, "Eroare de serviciu; încearcă mai târziu.") + detail) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise RuntimeError("Conexiunea către Gemini a eșuat sau a expirat; nu se reîncearcă automat.") from None
        candidates = obj.get("candidates", [])
        if not candidates or candidates[0].get("finishReason") != "STOP":
            raise RuntimeError("Gemini nu a returnat un răspuns complet (blocare, limită de tokeni sau altă oprire).")
        text = "".join(part.get("text", "") for part in candidates[0].get("content", {}).get("parts", [])
                       if not part.get("thought"))
        if not text.strip():
            raise RuntimeError("Gemini a returnat text gol.")
        return text


def test_connection():
    client = GeminiClient()
    reply = client.ask('Returnează doar JSON-ul {"ok":true}.', json_output=True)
    if json.loads(reply) != {"ok": True}:
        raise ValueError("Răspunsul Gemini nu respectă testul de conexiune.")
    return {"ok": True, "provider": "gemini", "model": client.model,
            "billing_verified": False, "message": "API funcțional. Nivelul Free/Paid se verifică în AI Studio, nu prin acest test."}
