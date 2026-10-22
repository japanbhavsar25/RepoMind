"""Eval harness: hit@k + MRR for RepoMind retrieval (no Ollama needed)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from repomind.rag import RepoRAG  # noqa: E402


def retrieve_files(rag: RepoRAG, q: str, k: int = 5, hybrid: bool = False, rerank: bool = False) -> list[str]:
    docs, metas, _ids = rag.retrieve(q, top_k=k, hybrid=hybrid, rerank=rerank)
    return [m.get("file", "?") for m in metas]


def score(rag: RepoRAG, gold: list[dict], k: int, hybrid: bool, rerank: bool):
    import time

    hits = 0
    rr_sum = 0.0
    rows = []
    t0 = time.time()
    for item in gold:
        q = item["q"]
        expected = item["expected"]
        got = retrieve_files(rag, q, k=k, hybrid=hybrid, rerank=rerank)
        rank = None
        for i, f in enumerate(got, 1):
            if any(e in f or f in e for e in expected):
                rank = i
                break
        hits += int(rank is not None)
        rr_sum += (1.0 / rank) if rank else 0.0
        rows.append((q, expected, got[:3], rank))
    n = len(gold)
    return hits / n if n else 0, rr_sum / n if n else 0, time.time() - t0, rows


def main(db: str = ".repomind.db", k: int = 5, rerank: bool = False) -> int:
    gold_path = Path(__file__).parent / "gold.json"
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    rag = RepoRAG(Path(db))
    if rag.collection.count() == 0:
        print("No embeddings. Run 'repomind index .' then 'repomind embed' first.")
        return 2

    for label, hyb, rr in [("vector", False, False), ("hybrid", True, False)] + ([("hybrid+rerank", True, True)] if rerank else []):
        hitk, mrr, dt, rows = score(rag, gold, k, hyb, rr)
        print(f"eval[{label}]: n={len(gold)} k={k} hit@{k}={hitk:.3f} MRR={mrr:.3f} ({dt:.1f}s, chunks={rag.collection.count()})")
        for q, exp, got, rank in rows:
            mark = f"rank={rank}" if rank else "MISS"
            print(f" - [{mark}] Q={q!r} exp={exp} got={got}")
        print("")

    # Save vector run as canonical results.md
    hitk, mrr, dt, rows = score(rag, gold, k, False, False)
    h_hit, h_mrr, _, _ = score(rag, gold, k, True, False)

    out = REPO_ROOT / "eval" / "results.md"
    lines = [
        "# RepoMind Retrieval Eval",
        "",
        f"Chunks: {rag.collection.count()} | k={k} | vector hit@{k}={hitk:.3f} MRR={mrr:.3f} | hybrid hit@{k}={h_hit:.3f} MRR={h_mrr:.3f}",
        "",
        "| Question | Expected | Top-3 got | Rank |",
        "|---|---|---|---|",
    ]
    for q, exp, got, rank in rows:
        lines.append(f"| {q} | {','.join(exp)} | {','.join(got)} | {rank or '-'} |")
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=".repomind.db")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--rerank", action="store_true", help="Also eval hybrid+cross-encoder rerank (downloads ~80MB)")
    args = ap.parse_args()
    raise SystemExit(main(db=args.db, k=args.k, rerank=args.rerank))
