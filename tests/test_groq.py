"""Tests for the Groq LLM client and provider selection (HTTP is mocked, no network)."""

import pytest
from fastapi.testclient import TestClient

from backend.config import settings
from backend.main import app
from backend.services import qa_service as qa_module
from repomind.llm import GroqClient, GroqError, OllamaClient


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def test_groq_generate_returns_text_and_usage(monkeypatch):
    sent = {}

    def fake_post(url, json, headers, timeout):
        sent.update(url=url, json=json, headers=headers)
        return FakeResponse(200, {
            "choices": [{"message": {"content": "  The answer [a.py:1-2]  "}}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 30},
        })

    monkeypatch.setattr("repomind.llm.requests.post", fake_post)
    client = GroqClient(api_key="gsk_test", model="test-model")
    out = client.generate("question", system="be grounded")

    assert out == "The answer [a.py:1-2]"
    assert sent["headers"]["Authorization"] == "Bearer gsk_test"
    assert sent["json"]["model"] == "test-model"
    assert sent["json"]["messages"][0] == {"role": "system", "content": "be grounded"}
    assert client.last_usage["prompt_tokens"] == 120
    assert client.last_usage["completion_tokens"] == 30
    assert client.last_usage["latency_ms"] >= 0


@pytest.mark.parametrize(
    ("status", "message"),
    [(401, "rejected the API key"), (429, "rate limit"), (500, "returned an error")],
)
def test_groq_errors_are_friendly(monkeypatch, status, message):
    monkeypatch.setattr(
        "repomind.llm.requests.post",
        lambda *a, **k: FakeResponse(status, text="boom"),
    )
    with pytest.raises(GroqError, match=message):
        GroqClient(api_key="gsk_test").generate("q")


def test_provider_selection(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "auto")
    monkeypatch.setattr(settings, "groq_api_key", "")
    assert isinstance(qa_module.get_llm_client(), OllamaClient)

    monkeypatch.setattr(settings, "groq_api_key", "gsk_test")
    assert isinstance(qa_module.get_llm_client(), GroqClient)

    monkeypatch.setattr(settings, "llm_provider", "ollama")
    assert isinstance(qa_module.get_llm_client(), OllamaClient)


def test_ask_endpoint_uses_groq_and_reports_metrics(monkeypatch):
    monkeypatch.setattr(settings, "embed_on_index", True)
    client = TestClient(app)
    assert client.post("/api/repos/index?repo_id=ecommerce_sample").status_code == 200

    monkeypatch.setattr(settings, "llm_provider", "auto")
    monkeypatch.setattr(settings, "groq_api_key", "gsk_test")
    captured = {}

    def fake_generate(self, prompt, system=None, temperature=0.3):
        captured["prompt"] = prompt
        self.last_usage = {"prompt_tokens": 500, "completion_tokens": 80, "latency_ms": 640}
        return "Payments are processed in payments.py 【payments.py:1-5】."

    monkeypatch.setattr(GroqClient, "generate", fake_generate)
    res = client.post(
        "/api/ask?repo_id=ecommerce_sample",
        json={"question": "how are payments processed?"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["model_used"] == settings.groq_model
    assert data["answer"] == "Payments are processed in payments.py [payments.py:1-5]."
    assert data["latency_ms"] == 640
    assert data["prompt_tokens"] == 500
    assert data["chunks_retrieved"] > 0
    assert "CODE CONTEXT" in captured["prompt"]
    # Citations carry real line numbers from the retrieved chunks, not a 1-1 placeholder
    assert any(c["line_end"] > 1 for c in data["citations"])
