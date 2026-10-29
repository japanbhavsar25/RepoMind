"""Eval harness: hit@k + MRR for RepoMind retrieval (no LLM needed).

Scores three retrieval setups against eval/gold.json, split by query kind
("natural" questions vs "identifier" lookups like `verify_citations`).
With --check, exits 1 if the live-demo setup drops below eval/thresholds.json,
which is what the CI eval gate runs.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from repomind.hybrid import _CROSS_ENCODER_CACHE, _CROSS_ENCODER_UNAVAILABLE, CrossEncoderReranker  # noqa: E402
from repomind.rag import RepoRAG  # noqa: E402

# (label, hybrid, rerank). The last one is what the live demo serves.
CONFIGS = [("vector", False, False), ("hybrid", True, False), ("hybrid+rerank", True, True)]
LIVE_CONFIG = "hybrid+rerank"


def retrieve_files(rag: RepoRAG, q: str, k: int = 5, hybrid: bool = False, rerank: bool = False) -> list[str]:
    docs, metas, _ids = rag.retrieve(q, top_k=k, hybrid=hybrid, rerank=rerank)
    return [m.get("file", "?") for m in metas]


def _metrics(rows: list[tuple]) -> dict:
    n = len(rows)
    if not n:
        return {"n": 0, "hit@1": 0.0, "hit@k": 0.0, "mrr": 0.0}
    ranks = [r[-1] for r in rows]
    return {
        "n": n,
        "hit@1": sum(1 for r in ranks if r == 1) / n,
        "hit@k": sum(1 for r in ranks if r) / n,
        "mrr": sum(1.0 / r for r in ranks if r) / n,
    }


def score(rag: RepoRAG, gold: list[dict], k: int, hybrid: bool, rerank: bool):
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
        rows.append((item.get("kind", "natural"), q, expected, got[:3], rank))
    by_kind = {"all": _metrics(rows)}
    for kind in sorted({r[0] for r in rows}):
        by_kind[kind] = _metrics([r for r in rows if r[0] == kind])
    return by_kind, time.time() - t0, rows


def check(results: dict, thresholds_path: Path, k: int) -> list[str]:
    """Return a list of failures: live-config metrics below their minimums."""
    spec = json.loads(thresholds_path.read_text(encoding="utf-8"))
    by_kind = results[spec.get("config", LIVE_CONFIG)]
    failures = []
    for kind, mins in spec["min"].items():
        got = by_kind.get(kind)
        if got is None:
            failures.append(f"{kind}: no gold queries of this kind")
            continue
        for metric, floor in mins.items():
            value = got[metric.replace(f"@{k}", "@k")]
            if value < floor:
                failures.append(f"{kind} {metric}={value:.3f} < {floor:.3f}")
    return failures


def main(db: str = ".repomind.db", k: int = 5, reranker: str = "auto", thresholds: Path | None = None) -> int:
    gold_path = Path(__file__).parent / "gold.json"
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    rag = RepoRAG(Path(db))
    if rag.collection.count() == 0:
        print("No embeddings. Run 'repomind index .' then 'repomind embed' first.")
        return 2

    model_name = CrossEncoderReranker().model_name
    if reranker == "lexical":
        # Same fallback the slim (no-PyTorch) live deployment takes
        _CROSS_ENCODER_UNAVAILABLE.add(model_name)

    results: dict[str, dict] = {}
    live_rows = []
    for label, hyb, rr in CONFIGS:
        by_kind, dt, rows = score(rag, gold, k, hyb, rr)
        results[label] = by_kind
        if label == LIVE_CONFIG:
            live_rows = rows
        print(f"eval[{label}] ({dt:.1f}s, chunks={rag.collection.count()})")
        for kind, m in by_kind.items():
            print(f"  {kind:<10} n={m['n']:<3} hit@1={m['hit@1']:.3f} hit@{k}={m['hit@k']:.3f} MRR={m['mrr']:.3f}")
        for kind, q, exp, got, rank in rows:
            mark = f"rank={rank}" if rank else "MISS"
            print(f" - [{mark}] ({kind}) Q={q!r} exp={exp} got={got}")
        print("")

    used = "cross-encoder" if model_name in _CROSS_ENCODER_CACHE else "lexical"
    lines = [
        "# RepoMind Retrieval Eval",
        "",
        f"Chunks: {rag.collection.count()} | k={k} | reranker: {used} | embeddings: {os.environ.get('REPOMIND_EMBED_BACKEND', 'auto')}",
        "",
        f"| Setup | Slice | n | Hit@1 | Hit@{k} | MRR@{k} |",
        "|---|---|---|---|---|---|",
    ]
    for label, by_kind in results.items():
        for kind, m in by_kind.items():
            lines.append(f"| {label} | {kind} | {m['n']} | {m['hit@1']:.2f} | {m['hit@k']:.2f} | {m['mrr']:.2f} |")
    lines += [
        "",
        f"## Per-question results ({LIVE_CONFIG}, the live demo setup)",
        "",
        "| Kind | Question | Expected | Top-3 got | Rank |",
        "|---|---|---|---|---|",
    ]
    for kind, q, exp, got, rank in live_rows:
        lines.append(f"| {kind} | {q} | {','.join(exp)} | {','.join(got)} | {rank or '-'} |")
    report = "\n".join(lines) + "\n"
    out = REPO_ROOT / "eval" / "results.md"
    out.write_text(report, encoding="utf-8")
    print(f"wrote {out}")

    if thresholds is None:
        return 0
    failures = check(results, thresholds, k)
    verdict = "FAILED" if failures else "passed"
    summary = f"## Retrieval eval gate {verdict}\n\n" + "".join(f"- {f}\n" for f in failures) + "\n" + report
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write(summary)
    if failures:
        print("Eval gate FAILED:\n  " + "\n  ".join(failures))
        return 1
    print("Eval gate passed.")
    return 0


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=".repomind.db")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument(
        "--reranker", choices=["auto", "lexical"], default="auto",
        help="auto: cross-encoder if sentence-transformers is installed; lexical: the slim live-demo fallback",
    )
    ap.add_argument("--check", type=Path, metavar="THRESHOLDS", help="Fail (exit 1) below these minimums")
    args = ap.parse_args()
    raise SystemExit(main(db=args.db, k=args.k, reranker=args.reranker, thresholds=args.check))
