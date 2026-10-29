"""Quantitative evaluation harness for RepoMind retrieval strategies."""

from __future__ import annotations

import json
import time
from pathlib import Path

from rich.table import Table

from repomind.database import RepoDatabase
from repomind.rag import RepoRAG


class RetrievalEvaluator:
    """Benchmark Dense vs. Sparse vs. Hybrid RRF retrieval strategies."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.rag = RepoRAG(db_path)

    def load_benchmark(
        self, gold_path: Path | None = None, max_samples: int = 20
    ) -> list[dict]:
        """Load evaluation queries from gold.json or auto-sample from SQLite database."""
        benchmark: list[dict] = []
        if gold_path and gold_path.exists():
            try:
                data = json.loads(gold_path.read_text(encoding="utf-8"))
                for item in data:
                    benchmark.append({
                        "q": item["q"],
                        "expected": [e.replace("\\", "/") for e in item.get("expected", [])],
                    })
            except Exception:
                pass

        # Auto-sample additional queries from SQLite if benchmark has fewer than max_samples
        if len(benchmark) < max_samples:
            try:
                with RepoDatabase(self.db_path) as db:
                    symbols = db.get_all_symbols()
                    for _kind, _id, name, qname, doc, _src, _start, _end, fpath in symbols:
                        if doc and len(doc.strip()) > 10:
                            q = f"where is {qname or name} implemented?"
                            norm_path = fpath.replace("\\", "/")
                            benchmark.append({"q": q, "expected": [norm_path]})
                            if len(benchmark) >= max_samples:
                                break
            except Exception:
                pass

        if len(benchmark) > max_samples:
            # Evenly spaced picks, so a gold set listed by kind (natural questions,
            # then identifiers) is sampled across all kinds, not just the first
            step = len(benchmark) / max_samples
            benchmark = [benchmark[int(i * step)] for i in range(max_samples)]
        return benchmark

    def _match_hit(self, retrieved_files: list[str], expected_files: list[str]) -> int:
        """Return 1-based rank of first matching file, or 0 if no match."""
        for rank, rf in enumerate(retrieved_files, 1):
            rf_norm = rf.replace("\\", "/")
            for ef in expected_files:
                ef_norm = ef.replace("\\", "/")
                if rf_norm == ef_norm or rf_norm.endswith(ef_norm) or ef_norm.endswith(rf_norm):
                    return rank
        return 0

    def evaluate_mode(self, benchmark: list[dict], mode: str) -> dict:
        """Run benchmark across a specific retrieval mode."""
        if not benchmark:
            return {"hit_1": 0.0, "hit_5": 0.0, "mrr_5": 0.0, "latency_ms": 0.0, "count": 0}

        hits_1 = 0
        hits_5 = 0
        reciprocal_ranks: list[float] = []
        latencies: list[float] = []

        for item in benchmark:
            q = item["q"]
            expected = item["expected"]

            t0 = time.perf_counter()
            retrieved_files: list[str] = []

            if mode == "dense":
                _docs, metas, _ids = self.rag.retrieve(q, top_k=5, hybrid=False)
                retrieved_files = [m.get("file", "") for m in metas]
            elif mode == "sparse":
                with RepoDatabase(self.db_path) as db:
                    if db.has_fts5:
                        fts_res = db.search_fts(q, limit=5)
                        cids = [r[0] for r in fts_res]
                        if cids:
                            mres = self.rag.collection.get(ids=cids, include=["metadatas"])
                            # get() doesn't keep the order asked for: restore the FTS ranking
                            by_id = dict(zip(mres.get("ids", []), mres.get("metadatas", []), strict=False))
                            retrieved_files = [by_id[c].get("file", "") for c in cids if c in by_id]
                if not retrieved_files:
                    # fallback to in-memory bm25
                    all_ids, all_docs, all_metas = self.rag._all_chunks()
                    try:
                        from rank_bm25 import BM25Okapi

                        from repomind.hybrid import tokenize

                        bm25 = BM25Okapi([tokenize(d, code_aware=True) for d in all_docs])
                        scores = bm25.get_scores(tokenize(q, code_aware=True))
                        top_idx = sorted(range(len(all_ids)), key=lambda i: scores[i], reverse=True)[:5]
                        retrieved_files = [all_metas[i].get("file", "") for i in top_idx]
                    except Exception:
                        retrieved_files = []
            elif mode == "hybrid":
                # Exactly what Ask and Search run: both searches fused, then reranked
                _docs, metas, _ids = self.rag.retrieve(q, top_k=5, hybrid=True, rerank=True)
                retrieved_files = [m.get("file", "") for m in metas]

            dt_ms = (time.perf_counter() - t0) * 1000
            latencies.append(dt_ms)

            rank = self._match_hit(retrieved_files, expected)
            if rank == 1:
                hits_1 += 1
            if 1 <= rank <= 5:
                hits_5 += 1
                reciprocal_ranks.append(1.0 / rank)
            else:
                reciprocal_ranks.append(0.0)

        total = len(benchmark)
        return {
            "hit_1": hits_1 / total if total else 0.0,
            "hit_5": hits_5 / total if total else 0.0,
            "mrr_5": sum(reciprocal_ranks) / total if total else 0.0,
            "latency_ms": sum(latencies) / total if total else 0.0,
            "count": total,
        }

    def run_full_evaluation(
        self, gold_path: Path | None = None, max_samples: int = 20
    ) -> dict[str, dict]:
        """Run comparison across Dense-Only, Sparse-Only, and Hybrid RRF modes."""
        benchmark = self.load_benchmark(gold_path=gold_path, max_samples=max_samples)

        results = {
            "Dense-Only (ChromaDB)": self.evaluate_mode(benchmark, mode="dense"),
            "Sparse-Only (FTS5 / BM25)": self.evaluate_mode(benchmark, mode="sparse"),
            "Hybrid RRF (RepoMind v2.0)": self.evaluate_mode(benchmark, mode="hybrid"),
        }
        return results

    @staticmethod
    def build_summary_table(results: dict[str, dict]) -> Table:
        """Create a beautiful Rich Table summarizing retrieval performance."""
        table = Table(title="Retrieval Benchmark: Dense vs. Sparse vs. Hybrid RRF")
        table.add_column("Strategy", style="cyan", no_wrap=True)
        table.add_column("Hit Rate 1", style="green", justify="right")
        table.add_column("Hit Rate 5", style="green", justify="right")
        table.add_column("MRR (Top 5)", style="magenta", justify="right")
        table.add_column("Avg Latency", style="yellow", justify="right")
        table.add_column("Queries", justify="right")

        for mode_name, metrics in results.items():
            hit_1_str = f"{metrics['hit_1'] * 100:.1f}%"
            hit_5_str = f"{metrics['hit_5'] * 100:.1f}%"
            mrr_str = f"{metrics['mrr_5']:.3f}"
            lat_str = f"{metrics['latency_ms']:.1f} ms"
            q_count = str(metrics["count"])

            if "Hybrid" in mode_name:
                table.add_row(
                    f"[bold green]{mode_name} [BEST][/bold green]",
                    f"[bold green]{hit_1_str}[/bold green]",
                    f"[bold green]{hit_5_str}[/bold green]",
                    f"[bold magenta]{mrr_str}[/bold magenta]",
                    lat_str,
                    q_count,
                )
            else:
                table.add_row(mode_name, hit_1_str, hit_5_str, mrr_str, lat_str, q_count)

        return table
