"""Model Context Protocol (MCP) server for RepoMind.

Exposes 4 AI tools over stdio JSON-RPC 2.0 to AI IDEs (Antigravity, Cursor, Claude Desktop):
1. repomind_search
2. repomind_symbol_lookup
3. repomind_blast_radius
4. repomind_health_summary
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from repomind.database import RepoDatabase
from repomind.git_analyzer import GitAnalyzer
from repomind.graph_builder import GraphBuilder, best_symbol_match, symbol_complexity
from repomind.rag import RepoRAG
from repomind.report import HOTSPOTS_SCORED, architecture_health_score

INVALID_PARAMS = -32602  # JSON-RPC error code for bad tool names or arguments
_JSON_TYPES = {"string": str, "integer": int}


class ToolArgumentError(ValueError):
    """A tools/call named an unknown tool or sent arguments that don't fit its schema."""


class RepoMindMCPServer:
    """Zero-dependency stdio JSON-RPC 2.0 Model Context Protocol (MCP) server."""

    def __init__(self, db_path: Path = Path(".repomind.db"), repo_path: Path = Path(".")) -> None:
        self.db_path = db_path
        self.repo_path = repo_path
        self._rag: RepoRAG | None = None

    @property
    def rag(self) -> RepoRAG:
        if self._rag is None:
            self._rag = RepoRAG(self.db_path)
        return self._rag

    def get_tools_list(self) -> list[dict]:
        """Return MCP tools definitions."""
        return [
            {
                "name": "repomind_search",
                "description": "Search the Python codebase using Hybrid RRF (dense semantic + sparse BM25) retrieval. Returns relevant code chunks with exact file paths and line ranges.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language question or code identifier query",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Number of code chunks to retrieve (default: 5)",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "repomind_symbol_lookup",
                "description": "Look up a function or class symbol in the codebase. Returns AST signature, docstring, cyclomatic complexity, file path, line numbers, and callers.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "symbol_name": {
                            "type": "string",
                            "description": "Name or qualified name of function/class to look up",
                        },
                    },
                    "required": ["symbol_name"],
                },
            },
            {
                "name": "repomind_blast_radius",
                "description": "Analyze the downstream blast radius and impact for a file or symbol. Returns direct importers, transitive dependents, PageRank centrality, cyclomatic complexity, and callers.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "string",
                            "description": "File path (e.g. 'parser.py') or symbol name to analyze",
                        },
                    },
                    "required": ["target"],
                },
            },
            {
                "name": "repomind_health_summary",
                "description": "Get an architectural and codebase health summary. Returns Health Score (0-100), circular dependency cycles, orphan files, top hotspots, and bus factor risks.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
        ]

    def validate_arguments(self, name: str, arguments: object) -> dict:
        """Check a call against the tool's ``inputSchema``; raise ToolArgumentError if it doesn't fit."""
        tool = next((t for t in self.get_tools_list() if t["name"] == name), None)
        if tool is None:
            raise ToolArgumentError(f"Unknown tool: {name}")
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            raise ToolArgumentError("'arguments' must be an object")
        schema = tool["inputSchema"]
        for key in schema.get("required", []):
            if not arguments.get(key):
                raise ToolArgumentError(f"Missing required argument '{key}'")
        for key, spec in schema.get("properties", {}).items():
            if key not in arguments:
                continue
            value = arguments[key]
            # bool is a subclass of int in Python, but true isn't a number in JSON
            if not isinstance(value, _JSON_TYPES[spec["type"]]) or isinstance(value, bool):
                raise ToolArgumentError(f"Argument '{key}' must be a {spec['type']}")
        if "top_k" in arguments and not 1 <= arguments["top_k"] <= 50:
            raise ToolArgumentError("Argument 'top_k' must be between 1 and 50")
        return arguments

    def handle_tool_call(self, name: str, arguments: dict) -> str:
        """Dispatch and execute an MCP tool call."""
        if not self.db_path.exists():
            return "Error: Database .repomind.db does not exist. Run 'repomind index' and 'repomind embed' first."

        if name == "repomind_search":
            query = arguments.get("query", "")
            top_k = int(arguments.get("top_k", 5))
            docs, metas, _ = self.rag.retrieve(query, top_k=top_k, hybrid=True)
            if not docs:
                return f"No code chunks matched query: '{query}'"
            parts = []
            for i, (doc, meta) in enumerate(zip(docs, metas, strict=False), 1):
                f = meta.get("file", "?")
                s = meta.get("start", "?")
                e = meta.get("end", "?")
                sym = meta.get("name", "?")
                parts.append(f"### Result {i}: {sym} ({f}:{s}-{e})\n{doc}\n")
            return "\n".join(parts)

        elif name == "repomind_symbol_lookup":
            symbol = arguments.get("symbol_name", "")
            with RepoDatabase(self.db_path) as db:
                matches = db.search(symbol, limit=500)
                if not matches:
                    return f"Symbol '{symbol}' not found in database."
                # The exact match first, then the closest substring matches
                best = best_symbol_match(matches, symbol)
                matches = [best] + [m for m in matches if m is not best][:4]
                output_blocks = []
                for match in matches:
                    kind, sname, qname, start, end, fpath = match
                    cc = symbol_complexity(db.get_function_complexities(file_path=fpath), sname, qname)
                    callers = db.get_symbol_calls(callee_name=sname)
                    caller_lines = [
                        f"  * {c[1]} ({c[0]}:{c[3]})"
                        for c in callers[:10]
                    ]
                    callers_str = "\n".join(caller_lines) if caller_lines else "  None recorded"

                    output_blocks.append(
                        f"Symbol: {qname or sname} ({kind})\n"
                        f"File: {fpath}:{start}-{end}\n"
                        f"Cyclomatic Complexity: {cc}\n"
                        f"Direct Callers:\n{callers_str}\n"
                    )
                return "\n---\n".join(output_blocks)

        elif name == "repomind_blast_radius":
            target = arguments.get("target", "")
            builder = GraphBuilder(self.db_path, self.repo_path)
            builder.build()
            res = builder.compute_blast_radius(target)
            return json.dumps(res, indent=2)

        elif name == "repomind_health_summary":
            with RepoDatabase(self.db_path) as db:
                stats = db.get_stats()
                f_rows = db.get_function_complexities()
                complexities = {}
                for _n, _q, cc, fpath in f_rows:
                    complexities[fpath] = complexities.get(fpath, 0) + cc

            builder = GraphBuilder(self.db_path, self.repo_path)
            builder.build()
            graph_res = builder.analyze()

            git = GitAnalyzer(self.repo_path)
            git_stats = git.analyze() if git.is_valid() else {}
            ghosts = git.get_ghost_files(git_stats, days=180) if git.is_valid() else []

            hotspots = GitAnalyzer.compute_composite_hotspots(
                git_stats, complexities, graph_res.get("pagerank", {})
            )[:HOTSPOTS_SCORED]

            # Same formula and inputs as the HTML report, so the two always agree
            score = architecture_health_score(
                len(graph_res.get("cycles", [])), len(graph_res.get("orphans", [])), hotspots, len(ghosts)
            )

            summary = {
                "health_score": score,
                "stats": stats,
                "cycles": graph_res.get("cycles", []),
                "orphans": graph_res.get("orphans", []),
                "top_hotspots": hotspots[:10],
                "ghost_files_count": len(ghosts),
            }
            return json.dumps(summary, indent=2)

        return f"Unknown tool: {name}"

    def run_stdio(self) -> None:
        """Run standard I/O JSON-RPC loop."""
        stdin = sys.stdin
        stdout = sys.stdout

        while True:
            line = stdin.readline()
            if not line:
                break
            line_str = line.strip()
            if not line_str:
                continue

            # Handle Content-Length framing if present
            if line_str.startswith("Content-Length:"):
                try:
                    length = int(line_str.split(":", 1)[1].strip())
                    # Consume following blank line
                    stdin.readline()
                    raw_body = stdin.read(length)
                    data = json.loads(raw_body)
                except Exception:
                    continue
            else:
                try:
                    data = json.loads(line_str)
                except Exception:
                    continue

            if not isinstance(data, dict):
                continue
            req_id = data.get("id")
            method = data.get("method")
            params = data.get("params") or {}

            # Notification or response
            if req_id is None:
                continue

            if method == "initialize":
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "repomind-mcp", "version": "2.0.0"},
                    },
                }
            elif method == "tools/list":
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"tools": self.get_tools_list()},
                }
            elif method == "tools/call":
                res = self._call_tool(req_id, params)
            elif method == "ping":
                res = {"jsonrpc": "2.0", "id": req_id, "result": {}}
            else:
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                }

            out_bytes = (json.dumps(res) + "\n").encode("utf-8")
            stdout.buffer.write(out_bytes)
            stdout.buffer.flush()

    def _call_tool(self, req_id: object, params: dict) -> dict:
        """Run one tools/call. Bad input is a JSON-RPC error and a failing tool is an
        error result; neither stops the server, so one bad request can't end the session."""
        name = params.get("name", "")
        try:
            arguments = self.validate_arguments(name, params.get("arguments"))
        except ToolArgumentError as exc:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": INVALID_PARAMS, "message": str(exc)}}
        try:
            text, is_error = self.handle_tool_call(name, arguments), False
        except Exception as exc:
            text, is_error = f"Error running {name}: {exc}", True
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"content": [{"type": "text", "text": text}], "isError": is_error},
        }
