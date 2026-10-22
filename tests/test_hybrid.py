# tests/test_hybrid.py
from repomind.hybrid import CrossEncoderReranker, rrf_fuse, tokenize


def test_tokenize_lowercases_and_splits():
    assert tokenize("Hello Auth_User!") == ["hello", "auth_user"]


def test_rrf_fuse_prefers_top_ranks():
    scores = rrf_fuse([["a", "b", "c"], ["b", "a"]])
    assert scores["a"] > scores["c"]
    assert scores["b"] > scores["c"]


def test_reranker_fallback_without_model():
    rr = CrossEncoderReranker(model_name="nonexistent-model-xyz")
    order = rr.rerank("q", ["d1", "d2", "d3"], top_n=2)
    assert order == [0, 1]
    assert CrossEncoderReranker().rerank("q", [], top_n=5) == []
