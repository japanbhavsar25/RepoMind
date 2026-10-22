"""Build and analyze codebase dependency graphs."""

from __future__ import annotations

import html
import sys
from pathlib import Path, PurePosixPath

import networkx as nx
from pyvis.network import Network

from repomind.database import RepoDatabase


# Patch pyvis write_html to guarantee UTF-8 encoding across all platforms (notably Windows)
def _safe_write_html(self, name: str, notebook: bool = False) -> None:
    Path(name).write_text(self.generate_html(notebook=notebook), encoding="utf-8")

Network.write_html = _safe_write_html

MAX_CYCLES = 10


def _module_name_for_path(rel_path: str) -> str:
    """Convert 'pkg/sub/mod.py' to 'pkg.sub.mod'.

    An ``__init__.py`` names the package itself, not a module called
    ``__init__`` ('pkg/__init__.py' -> 'pkg'). Top-level ``__init__.py``
    maps to an empty string.
    """
    parts = PurePosixPath(rel_path).parts
    if parts[-1] == "__init__.py":
        return ".".join(parts[:-1])
    return ".".join([*parts[:-1], PurePosixPath(parts[-1]).stem])


class GraphBuilder:
    """Builds a dependency graph from indexed imports."""

    def __init__(self, db_path: Path, repo_path: Path) -> None:
        self.db_path = db_path
        self.repo_path = repo_path
        self.graph = nx.DiGraph()
        self._pagerank: dict[str, float] | None = None
        self.warnings: list[str] = []

    def build(self) -> None:
        """Construct the graph from SQLite imports."""
        self.warnings = []
        with RepoDatabase(self.db_path) as db:
            files = dict(db.get_files())  # id -> path
            imports = db.get_imports()

        for path in files.values():
            self.graph.add_node(path)

        # Build a lookup to resolve module names back to files.
        # Exact matches win; suffixes ('pkg.utils', 'utils') are fallbacks
        # because projects often import without the top-level prefix.
        exact_map: dict[str, str] = {}
        short_map: dict[str, str] = {}
        for path in files.values():
            module = _module_name_for_path(path)
            if module:
                if module in exact_map:
                    self.warnings.append(f"duplicate module {module}: {exact_map[module]} vs {path}")
                exact_map.setdefault(module, path)
            parts = module.split(".") if module else []
            for i in range(1, len(parts)):
                key = ".".join(parts[i:])
                if key in short_map and short_map[key] != path:
                    self.warnings.append(f"ambiguous short import {key!r}: {short_map[key]} vs {path} (first wins)")
                short_map.setdefault(key, path)

        def resolve(module_name: str) -> str | None:
            if module_name in exact_map:
                return exact_map[module_name]
            if module_name in short_map:
                return short_map[module_name]
            return None

        for file_id, module_name, imported_name, is_from_import in imports:
            source_file = files.get(file_id)
            if not source_file or not module_name:
                continue

            # 'from pkg import submodule' usually targets the submodule named
            # by the import; fall back to the package itself.
            target = None
            if is_from_import and imported_name:
                target = resolve(f"{module_name}.{imported_name}")
            if target is None:
                target = resolve(module_name)

            if target and target != source_file:
                self.graph.add_edge(source_file, target, type="internal")
            elif target is None:
                # Unresolved: stdlib is noise, skip it; keep third-party.
                if module_name.split(".")[0] in sys.stdlib_module_names:
                    continue
                self.graph.add_edge(source_file, f"ext:{module_name}", type="external")

    @property
    def pagerank(self) -> dict[str, float]:
        """PageRank scores, computed once and cached."""
        if self._pagerank is None:
            try:
                self._pagerank = nx.pagerank(self.graph)
            except Exception:
                self._pagerank = {}
        return self._pagerank

    def analyze(self) -> dict:
        """Calculate graph metrics. Always returns the same keys."""
        node_count = self.graph.number_of_nodes()
        if node_count == 0:
            return {
                "node_count": 0,
                "edge_count": 0,
                "pagerank": {},
                "orphans": [],
                "cycles": [],
            }

        # Orphans: files with no internal imports and no internal importers
        orphans = []
        for node in self.graph.nodes():
            if node.startswith("ext:"):
                continue
            internal_preds = [n for n in self.graph.predecessors(node) if not n.startswith("ext:")]
            internal_succs = [n for n in self.graph.successors(node) if not n.startswith("ext:")]
            if not internal_preds and not internal_succs:
                orphans.append(node)

        # Detect circular dependencies (stop after MAX_CYCLES — enumeration
        # is exponential, so we never list them all on large graphs)
        cycles: list[list[str]] = []
        try:
            for cycle in nx.simple_cycles(self.graph):
                cycles.append(cycle)
                if len(cycles) >= MAX_CYCLES:
                    break
        except Exception:
            cycles = []

        return {
            "node_count": node_count,
            "edge_count": self.graph.number_of_edges(),
            "pagerank": self.pagerank,
            "orphans": orphans,
            "cycles": cycles,
        }

    def compute_blast_radius(self, target: str) -> dict:
        """Compute the transitive downstream dependents and blast radius for a file or symbol.

        Returns impact metrics including direct importers, transitive dependents,
        PageRank centrality, cyclomatic complexity, caller relationships, and risk score.
        """
        # 1. Resolve whether target is a file or symbol
        matched_file: str | None = None
        target_norm = target.replace("\\", "/").strip()

        # Exact file match
        if target_norm in self.graph:
            matched_file = target_norm
        else:
            # Suffix/stem match for files (e.g. 'parser.py' matching 'repomind/parser.py')
            for node in self.graph.nodes():
                if not node.startswith("ext:") and (
                    node.endswith(f"/{target_norm}")
                    or node == target_norm
                    or Path(node).stem == target_norm
                    or Path(node).name == target_norm
                ):
                    matched_file = node
                    break

        symbol_info: dict | None = None
        callers: list[dict] = []

        with RepoDatabase(self.db_path) as db:
            if not matched_file:
                # Target is likely a function or class symbol
                matches = db.search(target, limit=10)
                if matches:
                    kind, name, qname, start, end, file_path = matches[0]
                    matched_file = file_path
                    funcs = db.get_function_complexities(file_path=file_path)
                    sym_cc = 1
                    for fn_name, fn_qname, cc, _ in funcs:
                        if fn_name == name or fn_qname == qname:
                            sym_cc = cc
                            break
                    symbol_info = {
                        "name": qname or name,
                        "kind": kind,
                        "file": file_path,
                        "lines": f"{start}-{end}",
                        "complexity": sym_cc,
                    }
                    raw_calls = db.get_symbol_calls(callee_name=name)
                    callers = [
                        {
                            "caller_file": r[0],
                            "caller_symbol": r[1],
                            "callee": r[2],
                            "line": r[3],
                        }
                        for r in raw_calls
                    ]
            else:
                # File matched: find callers of any functions in this file
                raw_calls = db.get_symbol_calls(file_path=matched_file)
                callers = [
                    {
                        "caller_file": r[0],
                        "caller_symbol": r[1],
                        "callee": r[2],
                        "line": r[3],
                    }
                    for r in raw_calls
                ]

        direct_importers: list[str] = []
        transitive_dependents: list[str] = []
        pr_score = 0.0

        if matched_file and matched_file in self.graph:
            direct_importers = sorted(
                n for n in self.graph.predecessors(matched_file) if not n.startswith("ext:")
            )
            transitive_dependents = sorted(
                n for n in nx.ancestors(self.graph, matched_file) if not n.startswith("ext:")
            )
            pr_score = self.pagerank.get(matched_file, 0.0)

        # Retrieve function complexities in matched file
        complexities: list[dict] = []
        max_cc = 1
        total_cc = 0
        avg_cc = 1.0

        if matched_file:
            with RepoDatabase(self.db_path) as db:
                f_rows = db.get_function_complexities(file_path=matched_file)
                if f_rows:
                    complexities = [
                        {"name": r[1] or r[0], "complexity": r[2]}
                        for r in f_rows
                    ]
                    max_cc = max(r[2] for r in f_rows)
                    total_cc = sum(r[2] for r in f_rows)
                    avg_cc = total_cc / len(f_rows)

        # Risk level determination
        blast_count = len(transitive_dependents)
        if blast_count >= 10 or (blast_count >= 5 and max_cc >= 12) or pr_score > 0.15:
            risk = "CRITICAL"
        elif blast_count >= 5 or max_cc >= 8 or pr_score > 0.08:
            risk = "HIGH"
        elif blast_count >= 2 or max_cc >= 4:
            risk = "MEDIUM"
        else:
            risk = "LOW"

        return {
            "target": target,
            "target_type": "symbol" if symbol_info else "file",
            "file": matched_file or target,
            "symbol": symbol_info,
            "direct_importers": direct_importers,
            "transitive_dependents": transitive_dependents,
            "blast_radius_count": blast_count,
            "pagerank": pr_score,
            "complexity": {
                "max": max_cc,
                "total": total_cc,
                "average": avg_cc,
                "symbols": complexities[:10],
            },
            "callers": callers[:20],
            "risk_level": risk,
        }

    def to_pyvis(self, git_stats: dict[str, dict] | None = None) -> Network:
        """Generate a self-contained interactive PyVis network."""
        net = Network(
            height="900px",
            width="100%",
            directed=True,
            bgcolor="#0d1117",
            font_color="#c9d1d9",
            heading="RepoMind Dependency Graph",
            cdn_resources="in_line",  # single-file HTML, works offline
        )

        max_pr = max(self.pagerank.values(), default=1)
        if max_pr <= 0:
            max_pr = 1

        for node in self.graph.nodes():
            if node.startswith("ext:"):
                label = node[4:]
                color = "#484f58"
                size = 8
                title = f"External: {label}"
            else:
                label = Path(node).name
                stats = git_stats.get(node) if git_stats else None

                # Color by git activity
                if stats:
                    churn = stats.get("commit_count", 0)
                    if churn > 20:
                        color = "#da3633"  # hot red
                    elif churn > 5:
                        color = "#d29922"  # warm orange
                    else:
                        color = "#58a6ff"  # cool blue
                else:
                    color = "#58a6ff"

                pr = self.pagerank.get(node, 0)
                size = 20 + (pr / max_pr) * 40

                # vis.js renders tooltips as HTML — escape untrusted paths
                title = html.escape(node)
                if stats:
                    title += (
                        f"\nCommits: {stats.get('commit_count', 0)}"
                        f"\nAuthors: {stats.get('author_count', 0)}"
                    )

            net.add_node(node, label=label, color=color, size=size, title=title)

        for src, dst, data in self.graph.edges(data=True):
            edge_type = data.get("type", "internal")
            color = "#f85149" if edge_type == "external" else "#3fb950"
            width = 1 if edge_type == "external" else 2
            net.add_edge(src, dst, color=color, width=width, arrows="to")

        # Physics for pretty layout
        net.set_options("""
        {
          "physics": {
            "forceAtlas2Based": {
              "gravitationalConstant": -60,
              "centralGravity": 0.005,
              "springLength": 120,
              "springConstant": 0.18
            },
            "maxVelocity": 50,
            "solver": "forceAtlas2Based",
            "timestep": 0.35,
            "stabilization": {"iterations": 200}
          }
        }
        """)
        return net
