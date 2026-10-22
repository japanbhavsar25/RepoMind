"""Embedding layer: converts code into searchable vectors."""

from __future__ import annotations


class CodeEmbedder:
    """Handles embedding generation for ChromaDB storage (lazy load)."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        # Lazy: don't download/load on import or --help, only on first encode
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            # all-MiniLM-L6-v2: 22MB, CPU-friendly, good for short text
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Encode a batch of texts into vectors."""
        return self._load().encode(texts, show_progress_bar=False).tolist()
