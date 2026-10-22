"""Central config: defaults + optional repomind.yaml + env overrides."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RepoMindConfig:
    embed_model: str = "all-MiniLM-L6-v2"
    ollama_model: str = "phi3"
    ollama_url: str = "http://localhost:11434/api/generate"
    top_k: int = 5
    chunk_chars: int = 3000
    chunk_overlap: int = 300
    candidates_multiplier: int = 4


DEFAULTS = RepoMindConfig()


def load_config(path: Path | None = None) -> RepoMindConfig:
    """Load repomind.yaml if present, else defaults. No hard dependency on yaml."""
    cfg_path = path or Path("repomind.yaml")
    data: dict = {}
    if cfg_path.exists():
        try:
            import yaml  # type: ignore

            data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        except ImportError:
            # Minimal fallback: KEY: value lines
            for line in cfg_path.read_text(encoding="utf-8").splitlines():
                if ":" in line and not line.strip().startswith("#"):
                    k, v = line.split(":", 1)
                    data[k.strip()] = v.strip().strip("\"'")
        except Exception:
            data = {}
    # Only known keys, coerce ints
    out = {}
    for f in ("embed_model", "ollama_model", "ollama_url"):
        if f in data:
            out[f] = str(data[f])
    for f in ("top_k", "chunk_chars", "chunk_overlap", "candidates_multiplier"):
        if f in data:
            try:
                out[f] = int(data[f])
            except ValueError:
                pass
    return RepoMindConfig(**{**DEFAULTS.__dict__, **out})
