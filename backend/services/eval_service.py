"""Evaluation service running reproducible retrieval benchmarks."""

from __future__ import annotations

from backend.config import settings
from backend.services.repo_manager import repo_manager
from repomind.evaluator import RetrievalEvaluator


class EvalService:
    """Runs and caches quantitative retrieval benchmarks."""

    @staticmethod
    def run_eval(repo_id: str | None = None, max_samples: int = 15) -> dict:
        repo = repo_manager.get_repo(repo_id)
        if not repo.db_path.exists():
            return {
                "status": "error",
                "dataset_size": 0,
                "dense": {"hit_rate_at_1": 0.0, "hit_rate_at_5": 0.0, "mrr_at_5": 0.0, "avg_latency_ms": 0.0},
                "sparse": {"hit_rate_at_1": 0.0, "hit_rate_at_5": 0.0, "mrr_at_5": 0.0, "avg_latency_ms": 0.0},
                "hybrid": {"hit_rate_at_1": 0.0, "hit_rate_at_5": 0.0, "mrr_at_5": 0.0, "avg_latency_ms": 0.0},
            }

        evaluator = RetrievalEvaluator(repo.db_path)
        # The hand-labelled gold set is about RepoMind's own files; any other repo
        # gets only questions sampled from its own documented symbols.
        gold_file = settings.base_dir / "eval" / "gold.json"
        gold_path = gold_file if repo.id == "repomind_core" and gold_file.exists() else None

        raw = evaluator.run_full_evaluation(gold_path=gold_path, max_samples=max_samples)

        dense = raw.get("Dense-Only (ChromaDB)", {})
        sparse = raw.get("Sparse-Only (FTS5 / BM25)", {})
        hybrid = raw.get("Hybrid RRF (RepoMind v2.0)", {})

        return {
            "status": "success",
            "dataset_size": hybrid.get("count", 0),
            "dense": {
                "hit_rate_at_1": round(dense.get("hit_1", 0.0), 4),
                "hit_rate_at_5": round(dense.get("hit_5", 0.0), 4),
                "mrr_at_5": round(dense.get("mrr_5", 0.0), 4),
                "avg_latency_ms": round(dense.get("latency_ms", 0.0), 2),
            },
            "sparse": {
                "hit_rate_at_1": round(sparse.get("hit_1", 0.0), 4),
                "hit_rate_at_5": round(sparse.get("hit_5", 0.0), 4),
                "mrr_at_5": round(sparse.get("mrr_5", 0.0), 4),
                "avg_latency_ms": round(sparse.get("latency_ms", 0.0), 2),
            },
            "hybrid": {
                "hit_rate_at_1": round(hybrid.get("hit_1", 0.0), 4),
                "hit_rate_at_5": round(hybrid.get("hit_5", 0.0), 4),
                "mrr_at_5": round(hybrid.get("mrr_5", 0.0), 4),
                "avg_latency_ms": round(hybrid.get("latency_ms", 0.0), 2),
            },
        }


eval_service = EvalService()
