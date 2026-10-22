"""GraphRAG: expand vector hits with 1-hop graph neighbors."""

from __future__ import annotations

from pathlib import Path


def graph_context_for_files(
    files: list[str], db_path: Path, repo_path: Path | None = None, max_neighbors: int = 6
) -> str:
    """Return 'Used by / Depends on' lines for retrieved files."""
    from repomind.graph_builder import GraphBuilder

    repo = repo_path or db_path.parent
    try:
        b = GraphBuilder(db_path, repo)
        b.build()
        g = b.graph
    except Exception:
        return ""
    lines: list[str] = []
    seen: set[str] = set()
    for f in files:
        if f not in g:
            continue
        try:
            succs = [n for n in g.successors(f) if not n.startswith("ext:")][:max_neighbors]
            preds = [n for n in g.predecessors(f) if not n.startswith("ext:")][:max_neighbors]
        except Exception:
            continue
        for s in succs:
            key = (f, s)
            if key not in seen:
                seen.add(key)
                lines.append(f"{f} depends on {s}")
        for p in preds:
            key = (p, f)
            if key not in seen:
                seen.add(key)
                lines.append(f"{p} uses {f}")
        if len(lines) >= max_neighbors * 2:
            break
    if not lines:
        return ""
    return "GRAPH NEIGHBORS (1-hop):\n" + "\n".join(f"- {line}" for line in lines[:12])
