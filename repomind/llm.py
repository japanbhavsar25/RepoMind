"""LLM clients: local Ollama, or the hosted Groq API."""

from __future__ import annotations

import os
from pathlib import Path

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


GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqError(RuntimeError):
    """Raised when the Groq API cannot be reached or returns an error."""


class GroqClient:
    """Thin wrapper around Groq's OpenAI-compatible chat completions API.

    After each ``generate`` call, ``last_usage`` holds token counts and latency
    so callers can report cost/latency per answer.
    """

    def __init__(self, api_key: str, model: str = "openai/gpt-oss-120b", url: str = GROQ_URL) -> None:
        self.api_key = api_key
        self.model = model
        self.url = url
        self.last_usage: dict = {}

    def is_alive(self) -> bool:
        """Groq is a hosted API: treat it as available whenever a key is configured."""
        return bool(self.api_key)

    def generate(self, prompt: str, system: str | None = None, temperature: float = 0.3) -> str:
        """Send a prompt to Groq and return the response text."""
        import time

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {"model": self.model, "messages": messages, "temperature": temperature}
        headers = {"Authorization": f"Bearer {self.api_key}"}

        start = time.perf_counter()
        try:
            response = requests.post(self.url, json=payload, headers=headers, timeout=60)
        except requests.exceptions.Timeout as e:
            raise GroqError("Groq timed out. Please try again.") from e
        except requests.exceptions.RequestException as e:
            raise GroqError(f"Cannot reach Groq: {e}") from e

        if response.status_code == 401:
            raise GroqError("Groq rejected the API key. Check GROQ_API_KEY in your .env file.")
        if response.status_code == 429:
            raise GroqError("Groq rate limit reached. Wait a minute and try again.")
        if not response.ok:
            raise GroqError(f"Groq returned an error ({response.status_code}): {response.text[:200]}")

        data = response.json()
        usage = data.get("usage") or {}
        self.last_usage = {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "latency_ms": round((time.perf_counter() - start) * 1000),
        }
        return data["choices"][0]["message"]["content"].strip()


def env_setting(name: str, env_file: Path = Path(".env")) -> str:
    """Read a setting from the environment, else from a ``NAME=value`` line in ``.env``."""
    if os.environ.get(name):
        return os.environ[name]
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() == name:
                return value.strip().strip("\"'")
    return ""


def default_llm_client(ollama_model: str, ollama_url: str) -> GroqClient | OllamaClient:
    """Groq when GROQ_API_KEY is set (same rule as the web server), else local Ollama."""
    api_key = env_setting("GROQ_API_KEY")
    if api_key:
        return GroqClient(api_key=api_key, model=env_setting("GROQ_MODEL") or "openai/gpt-oss-120b")
    return OllamaClient(model=ollama_model, url=ollama_url)
