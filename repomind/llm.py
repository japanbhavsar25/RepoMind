"""Ollama LLM client for local inference."""

from __future__ import annotations

import requests

OLLAMA_URL = "http://localhost:11434/api/generate"


class OllamaError(RuntimeError):
    """Raised when Ollama cannot be reached or returns an error."""


class OllamaClient:
    """Thin wrapper around Ollama's HTTP API."""

    def __init__(self, model: str = "phi3", url: str = OLLAMA_URL) -> None:
        self.model = model
        self.url = url

    @property
    def base_url(self) -> str:
        """Server root, derived from the API URL (respects custom endpoints)."""
        return self.url.rsplit("/api/", 1)[0]

    def generate(self, prompt: str, system: str | None = None, temperature: float = 0.3) -> str:
        """Send a prompt to Ollama and return the response text.

        Raises :class:`OllamaError` instead of returning error strings so
        callers can distinguish failures from real answers.
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system

        try:
            response = requests.post(self.url, json=payload, timeout=120)
            response.raise_for_status()
            return response.json().get("response", "").strip()
        except requests.exceptions.ConnectionError as e:
            raise OllamaError(
                "Cannot connect to Ollama. Is it running? "
                "Run 'ollama serve' or keep the app open."
            ) from e
        except requests.exceptions.Timeout as e:
            raise OllamaError(
                "Ollama timed out. Try a smaller model or shorter prompt."
            ) from e
        except requests.exceptions.RequestException as e:
            raise OllamaError(f"Ollama request failed: {e}") from e

    def generate_stream(self, prompt: str, system: str | None = None, temperature: float = 0.3):
        """Yield response chunks as they arrive (for streaming UX)."""
        import json

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system
        try:
            with requests.post(self.url, json=payload, timeout=120, stream=True) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line.decode("utf-8"))
                    except Exception:
                        continue
                    if "response" in data:
                        yield data["response"]
                    if data.get("done"):
                        break
        except requests.exceptions.ConnectionError as e:
            raise OllamaError(
                "Cannot connect to Ollama. Is it running? "
                "Run 'ollama serve' or keep the app open."
            ) from e
        except requests.exceptions.Timeout as e:
            raise OllamaError("Ollama timed out. Try a smaller model or shorter prompt.") from e
        except requests.exceptions.RequestException as e:
            raise OllamaError(f"Ollama request failed: {e}") from e

    def is_alive(self) -> bool:
        """Check if Ollama is reachable (fast /api/tags probe)."""
        try:
            base = self.base_url.rstrip("/")
            # /api/tags is cheap and proves daemon + api; fallback to base root
            for url in (f"{base}/api/tags", base):
                try:
                    requests.get(url, timeout=2)
                    return True
                except Exception:
                    continue
            return False
        except Exception:
            return False
