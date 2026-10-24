"""Embedding layer: converts code into searchable vectors."""

from __future__ import annotations

# Loaded models shared across instances: loading takes seconds, and the web
# backend creates a new CodeEmbedder per request.
_MODEL_CACHE: dict[str, object] = {}


class CodeEmbedder:
    """Handles embedding generation for ChromaDB storage (lazy load)."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        # Lazy: don't download/load on import or --help, only on first encode
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            model = _MODEL_CACHE.get(self.model_name)
            if model is None:
                from sentence_transformers import SentenceTransformer

                # all-MiniLM-L6-v2: 22MB, CPU-friendly, good for short text
                model = SentenceTransformer(self.model_name)
                _MODEL_CACHE[self.model_name] = model
            self._model = model
        return self._model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Encode a batch of texts into vectors."""
        return self._load().encode(texts, show_progress_bar=False).tolist()
