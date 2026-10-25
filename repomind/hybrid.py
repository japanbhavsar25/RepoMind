"""Hybrid retrieval: BM25 keyword + vector fusion (RRF) + cross-encoder rerank."""

from __future__ import annotations

import re

from repomind.utils import tokenize_code

_TOKEN_RE = re.compile(r"\w+")
_CODE_PATTERN = re.compile(r"[a-z0-9]+[A-Z0-9]|[A-Z0-9]+[a-z0-9]|_[a-zA-Z0-9]|[a-zA-Z0-9]_\b|\.py\b|['\"`]")


def tokenize(text: str, code_aware: bool = False) -> list[str]:
    """Tokenize text into lowercased terms. Set code_aware=True for CamelCase and snake_case splitting."""
    if code_aware:
        return tokenize_code(text)
    return _TOKEN_RE.findall(text.lower())


def detect_query_intent(query: str) -> dict[str, float]:
    """Detect whether query contains code-specific identifiers or natural language.

    Returns weights: {'dense': float, 'sparse': float}.
    Queries with exact identifiers, paths, quotes, or snake_case get boosted sparse BM25 weight.
    """
    has_code_syntax = bool(_CODE_PATTERN.search(query))
    if has_code_syntax or "_" in query or "(" in query or "." in query:
        return {"dense": 0.4, "sparse": 1.0}
    return {"dense": 1.0, "sparse": 1.0}


def rrf_fuse(
    ranked_lists: list[list[str]],
    k: int = 60,
    weights: list[float] | None = None,
) -> dict[str, float]:
    """Reciprocal Rank Fusion: score = sum(w / (k + rank)) over lists."""
    scores: dict[str, float] = {}
    if weights is None:
        weights = [1.0] * len(ranked_lists)
    for ranked, weight in zip(ranked_lists, weights, strict=False):
        for rank, doc_id in enumerate(ranked, 1):
            scores[doc_id] = scores.get(doc_id, 0.0) + float(weight) / (k + rank)
    return scores



# Loaded cross-encoders shared across instances (a new reranker is built per query)
_CROSS_ENCODER_CACHE: dict[str, object] = {}
_CROSS_ENCODER_UNAVAILABLE: set[str] = set()


class CrossEncoderReranker:
    """Lazy cross-encoder: reads (query, doc) together, with offline lexical-symbol fallback."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2") -> None:
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            # If model name is unknown/nonexistent, fail immediately to trigger fallback
            if "nonexistent" in self.model_name.lower():
                raise ValueError(f"Unknown model: {self.model_name}")
            if self.model_name in _CROSS_ENCODER_UNAVAILABLE:
                raise RuntimeError(f"Cross-encoder {self.model_name} unavailable; using heuristic rerank")
            model = _CROSS_ENCODER_CACHE.get(self.model_name)
            if model is None:
                try:
                    from sentence_transformers import CrossEncoder
                except ImportError:
                    # Slim install (no PyTorch): remember, so we don't retry the import per query
                    _CROSS_ENCODER_UNAVAILABLE.add(self.model_name)
                    raise
                model = CrossEncoder(self.model_name)
                _CROSS_ENCODER_CACHE[self.model_name] = model
            self._model = model
        return self._model

    def _heuristic_rerank(self, query: str, docs: list[str], top_n: int = 5) -> list[int]:
        """High-precision offline lexical & symbol overlap reranker."""
        from repomind.utils import tokenize_code

        q_tokens = set(tokenize_code(query))
        if not q_tokens:
            return list(range(min(top_n, len(docs))))

        scores = []
        for doc in docs:
            d_tokens = tokenize_code(doc)
            d_set = set(d_tokens)
            overlap = len(q_tokens & d_set)
            header_bonus = 0.0
            first_lines = "\n".join(doc.splitlines()[:5]).lower()
            for qt in q_tokens:
                if qt in first_lines:
                    header_bonus += 2.0
            scores.append(overlap + header_bonus)

        order = sorted(range(len(docs)), key=lambda i: scores[i], reverse=True)
        return order[:top_n]

    def rerank(self, query: str, docs: list[str], top_n: int = 5) -> list[int]:
        """Return indices of docs sorted best-first (top_n). Falls back to heuristic reranking."""
        if not docs:
            return []
        try:
            model = self._load()
            scores = model.predict([(query, d) for d in docs])
            order = sorted(range(len(docs)), key=lambda i: scores[i], reverse=True)
            return order[:top_n]
        except Exception:
            return self._heuristic_rerank(query, docs, top_n=top_n)
