"""Embedding layer: converts code into searchable vectors."""

from __future__ import annotations

import importlib.util
import os
import threading

# Loaded models shared across instances: loading takes seconds, and the web
# backend creates a new CodeEmbedder per request.
_MODEL_CACHE: dict[str, object] = {}
# Startup warm-up and the first request can race to load (and download) the model
_MODEL_LOCK = threading.Lock()

ONNX_MODEL = "all-MiniLM-L6-v2"


def embed_backend() -> str:
    """Which runtime to embed with: "sentence-transformers" or "onnx".

    REPOMIND_EMBED_BACKEND overrides; by default sentence-transformers is used
    when installed, else ChromaDB's bundled ONNX MiniLM (no PyTorch, ~10x less
    memory — what the slim 512 MB deployment uses). Both produce the same
    all-MiniLM-L6-v2 384-d vectors.
    """
    choice = os.environ.get("REPOMIND_EMBED_BACKEND", "auto").lower()
    if choice in ("onnx", "sentence-transformers"):
        return choice
    if importlib.util.find_spec("sentence_transformers") is not None:
        return "sentence-transformers"
    return "onnx"


class _OnnxModel:
    """Adapter giving ChromaDB's ONNX MiniLM the same .encode() as SentenceTransformer.

    Tuned for small (512 MB) hosts: onnxruntime's CPU memory arena keeps the
    largest scratch buffer it ever allocated, and every input is padded to 256
    tokens, so embedding 32-chunk batches pinned ~430 MB. Arena off + batches
    of 8 keeps peak memory low at a small speed cost.
    """

    BATCH_SIZE = 8

    def __init__(self) -> None:
        from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

        fn = ONNXMiniLM_L6_V2()
        fn._download_model_if_not_exists()
        so = fn.ort.SessionOptions()
        so.log_severity_level = 3
        so.graph_optimization_level = fn.ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        so.enable_cpu_mem_arena = False
        so.enable_mem_pattern = False
        session = fn.ort.InferenceSession(
            os.path.join(fn.DOWNLOAD_PATH, fn.EXTRACTED_FOLDER_NAME, "model.onnx"),
            providers=["CPUExecutionProvider"],
            sess_options=so,
        )
        # `model` is a cached property on ChromaDB's class: pre-seed it with our session
        fn.__dict__["model"] = session
        self._fn = fn

    def encode(self, texts: list[str], show_progress_bar: bool = False):
        import numpy as np

        return np.array(self._fn._forward(texts, batch_size=self.BATCH_SIZE))


class CodeEmbedder:
    """Handles embedding generation for ChromaDB storage (lazy load)."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        # Lazy: don't download/load on import or --help, only on first encode
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            backend = embed_backend()
            key = f"{backend}:{self.model_name}"
            with _MODEL_LOCK:
                self._model = self._load_shared(backend, key)
        return self._model

    def _load_shared(self, backend: str, key: str):
        """Return the process-wide model for `key`, loading it once. Caller holds _MODEL_LOCK."""
        model = _MODEL_CACHE.get(key)
        if model is None:
            if backend == "onnx":
                if self.model_name != ONNX_MODEL:
                    raise ValueError(
                        f"The ONNX embedding backend only supports {ONNX_MODEL}, not {self.model_name}."
                    )
                model = _OnnxModel()
            else:
                from sentence_transformers import SentenceTransformer

                # all-MiniLM-L6-v2: 22MB, CPU-friendly, good for short text
                model = SentenceTransformer(self.model_name)
            _MODEL_CACHE[key] = model
        return model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Encode a batch of texts into vectors."""
        return self._load().encode(texts, show_progress_bar=False).tolist()
