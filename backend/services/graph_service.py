"""Architecture dependency graph and change-impact analysis service."""

from __future__ import annotations

from typing import Any

from backend.services.repo_manager import repo_manager
from repomind.graph_builder import GraphBuilder


class GraphService:
    """Computes dependency networks, PageRank metrics, and downstream blast radius."""

    @staticmethod
    def get_graph_data(repo_id: str | None = None) -> dict:
        repo = repo_manager.get_repo(repo_id)
        if not repo.db_path.exists():
            return {
                "nodes": [],
                "edges": [],
                "cycles": [],
                "orphans": [],
                "pagerank_leaderboard": [],
            }

        builder = GraphBuilder(repo.db_path, repo.root_path)
        builder.build()
        analysis = builder.analyze()

        orphans_set = set(analysis.get("orphans", []))
        pageranks = analysis.get("pagerank", {})

        nodes: list[dict[str, Any]] = []
        for n in builder.graph.nodes:
            is_ext = str(n).startswith("ext:")
            label = str(n)[4:] if is_ext else str(n)
            pr = round(pageranks.get(n, 0.0), 4)
            nodes.append({
                "id": str(n),
                "label": label,
                "type": "external" if is_ext else "internal",
                "pagerank": pr,
                "is_orphan": str(n) in orphans_set,
            })

        edges: list[dict[str, Any]] = []
        for u, v, data in builder.graph.edges(data=True):
            edges.append({
                "source": str(u),
                "target": str(v),
                "type": data.get("type", "internal"),
            })

        # Rank files by PageRank
        leaderboard = [
            {"file": k, "score": round(v, 4)}
            for k, v in sorted(pageranks.items(), key=lambda x: -x[1])
            if not str(k).startswith("ext:")
        ][:10]

        return {
            "nodes": nodes,
            "edges": edges,
            "cycles": analysis.get("cycles", []),
            "orphans": analysis.get("orphans", []),
            "pagerank_leaderboard": leaderboard,
        }

    @staticmethod
    def compute_impact(target: str, repo_id: str | None = None) -> dict:
        repo = repo_manager.get_repo(repo_id)
        if not repo.db_path.exists():
            return {
                "target": target,
                "found": False,
                "kind": "unknown",
                "direct_importers": [],
                "transitive_dependents": [],
                "pagerank": 0.0,
                "complexity": 0,
                "callers": [],
                "limitations": ["Repository database is not indexed"],
            }

        builder = GraphBuilder(repo.db_path, repo.root_path)
        builder.build()
        impact = builder.compute_blast_radius(target)

        found = bool(impact.get("file") in builder.graph or impact.get("symbol") is not None)
        target_kind = impact.get("target_type", "unknown")

        # Extract callers and complexity
        callers = impact.get("callers", [])
        comp_data = impact.get("complexity", {})
        complexity = comp_data.get("max", 0) if isinstance(comp_data, dict) else 0

        limitations = [
            "Static analysis captures explicit imports and direct AST calls only.",
            "Dynamic imports, reflection, and runtime monkey-patching are not inferred.",
            "Test coverage is mapped when test files import or reference the target.",
        ]

        return {
            "target": target,
            "found": found,
            "kind": target_kind,
            "direct_importers": impact.get("direct_importers", []),
            "transitive_dependents": impact.get("transitive_dependents", []),
            "pagerank": round(impact.get("pagerank", 0.0), 4),
            "complexity": complexity,
            "callers": callers,
            "limitations": limitations,
        }


graph_service = GraphService()
