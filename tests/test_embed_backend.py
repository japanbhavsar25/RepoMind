"""Tests for choosing the embedding runtime (sentence-transformers vs slim ONNX)."""

import pytest

from repomind import embedder


def test_env_override(monkeypatch):
    monkeypatch.setenv("REPOMIND_EMBED_BACKEND", "onnx")
    assert embedder.embed_backend() == "onnx"
    monkeypatch.setenv("REPOMIND_EMBED_BACKEND", "sentence-transformers")
    assert embedder.embed_backend() == "sentence-transformers"


def test_auto_falls_back_to_onnx_without_sentence_transformers(monkeypatch):
    monkeypatch.delenv("REPOMIND_EMBED_BACKEND", raising=False)
    monkeypatch.setattr(embedder.importlib.util, "find_spec", lambda name: None)
    assert embedder.embed_backend() == "onnx"


def test_onnx_backend_rejects_other_models(monkeypatch):
    monkeypatch.setenv("REPOMIND_EMBED_BACKEND", "onnx")
    monkeypatch.setattr(embedder, "_MODEL_CACHE", {})
    with pytest.raises(ValueError, match="only supports"):
        embedder.CodeEmbedder("some-other-model").embed_texts(["x"])


def test_reranker_falls_back_when_cross_encoder_missing(monkeypatch):
    import builtins

    from repomind import hybrid

    real_import = builtins.__import__

    def no_sentence_transformers(name, *args, **kwargs):
        if name.startswith("sentence_transformers"):
            raise ImportError("not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_sentence_transformers)
    monkeypatch.setattr(hybrid, "_CROSS_ENCODER_CACHE", {})
    monkeypatch.setattr(hybrid, "_CROSS_ENCODER_UNAVAILABLE", set())

    rr = hybrid.CrossEncoderReranker("fake/cross-encoder")
    docs = ["def unrelated(): pass", "def verify_signature(sig): return check(sig)"]
    assert rr.rerank("verify signature", docs, top_n=1) == [1]
    assert "fake/cross-encoder" in hybrid._CROSS_ENCODER_UNAVAILABLE
