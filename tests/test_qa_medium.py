"""Regression tests for the QA report's Medium findings (M2-M9)."""

import io
import json
import sys

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from backend.config import settings
from backend.main import app
from backend.routers import repos as repos_router
from backend.services.repo_manager import CloneFailedError, RepoManager, repo_manager
from repomind.cli import app as cli_app
from repomind.database import FunctionRecord, ImportRecord, RepoDatabase
from repomind.evaluator import RetrievalEvaluator
from repomind.graph_builder import GraphBuilder, best_symbol_match, symbol_complexity
from repomind.llm import GroqClient, OllamaClient, default_llm_client, env_setting
from repomind.mcp_server import RepoMindMCPServer
from repomind.parser import extract_file

client = TestClient(app)


# --- M2: the clone rate limit can't be dodged, and mistakes are free ----------

@pytest.fixture
def public(monkeypatch):
    monkeypatch.setattr(settings, "public_mode", True)
    monkeypatch.setattr(settings, "github_adds_per_hour", 2)
    monkeypatch.setattr(repos_router, "_github_adds", repos_router.defaultdict(repos_router.deque))
    before = set(repo_manager._registry)
    active = repo_manager._active_repo_id
    yield
    for repo_id in set(repo_manager._registry) - before:
        del repo_manager._registry[repo_id]
    repo_manager._active_repo_id = active


def _ok_clone(self, url, dest):
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "a.py").write_text("x = 1\n", encoding="utf-8")


def _add(name, forwarded):
    return client.post(
        "/api/repos/github", json={"url": f"https://github.com/acme/{name}"}, headers={"X-Forwarded-For": forwarded}
    )


def test_spoofed_forwarded_for_does_not_reset_the_limit(public, monkeypatch):
    monkeypatch.setattr(RepoManager, "_git_clone", _ok_clone)
    # The proxy appends the real address last; the first entries are the client's own
    assert _add("one", "10.0.0.1, 203.0.113.5").status_code == 201
    assert _add("two", "10.0.0.2, 203.0.113.5").status_code == 201
    assert _add("three", "10.0.0.3, 203.0.113.5").status_code == 429


def test_bad_links_and_failed_clones_use_no_quota(public, monkeypatch):
    def failing_clone(self, url, dest):
        raise CloneFailedError("Could not clone the repository.")

    monkeypatch.setattr(RepoManager, "_git_clone", failing_clone)
    ip = "198.51.100.7"
    for i in range(3):
        assert client.post("/api/repos/github", json={"url": "https://evil.example/a/b"},
                           headers={"X-Forwarded-For": ip}).status_code == 400
        assert _add(f"typo{i}", ip).status_code == 400
    monkeypatch.setattr(RepoManager, "_git_clone", _ok_clone)
    assert _add("real", ip).status_code == 201


def test_server_wide_cap(public, monkeypatch):
    monkeypatch.setattr(RepoManager, "_git_clone", _ok_clone)
    monkeypatch.setattr(settings, "github_adds_per_hour_total", 2)
    assert _add("a", "203.0.113.1").status_code == 201
    assert _add("b", "203.0.113.2").status_code == 201
    assert _add("c", "203.0.113.3").status_code == 429


# --- M3: imports resolve to the importer's own folder first --------------------

def test_short_import_prefers_the_sibling_module(tmp_path):
    db_path = tmp_path / "g.db"
    with RepoDatabase(db_path) as db:
        for path in ("repomind/utils.py", "samples/shop/auth.py", "samples/shop/utils.py"):
            db.insert_file(path, "h", 1, 0.0)
        db.insert_imports([ImportRecord(2, "utils", "slugify", True, 1)])  # in samples/shop/auth.py
        db.commit()
    builder = GraphBuilder(db_path, tmp_path)
    builder.build()
    assert list(builder.graph.successors("samples/shop/auth.py")) == ["samples/shop/utils.py"]


# --- M4: the symbol you named, with its own complexity -------------------------

def test_exact_symbol_beats_substring_match():
    rows = [("function", "hash_token_v2", "hash_token_v2", 1, 2, "a.py"), ("function", "hash", "hash", 5, 6, "a.py")]
    assert best_symbol_match(rows, "hash")[1] == "hash"
    assert best_symbol_match(rows, "has")[1] == "hash_token_v2"
    assert best_symbol_match([], "x") is None


def test_complexity_is_looked_up_by_qualified_name():
    funcs = [("__init__", "Busy.__init__", 5, "a.py"), ("__init__", "Simple.__init__", 1, "a.py")]
    assert symbol_complexity(funcs, "__init__", "Simple.__init__") == 1
    assert symbol_complexity(funcs, "__init__", "Busy.__init__") == 5


@pytest.fixture
def symbols_db(tmp_path):
    db_path = tmp_path / "s.db"
    with RepoDatabase(db_path) as db:
        fid = db.insert_file("a.py", "h", 20, 0.0)
        db.insert_functions([
            FunctionRecord(fid, "hash_token_v2", "hash_token_v2", 1, 3, None, "", complexity=7),
            FunctionRecord(fid, "hash", "hash", 5, 6, None, "", complexity=2),
            FunctionRecord(fid, "__init__", "Busy.__init__", 8, 12, None, "", complexity=5),
            FunctionRecord(fid, "__init__", "Simple.__init__", 14, 15, None, "", complexity=1),
        ])
        db.commit()
    return db_path


def test_blast_radius_picks_the_named_symbol(symbols_db, tmp_path):
    builder = GraphBuilder(symbols_db, tmp_path)
    builder.build()
    assert builder.compute_blast_radius("hash")["symbol"]["name"] == "hash"
    assert builder.compute_blast_radius("Simple.__init__")["symbol"]["complexity"] == 1
    out = RepoMindMCPServer(db_path=symbols_db).handle_tool_call("repomind_symbol_lookup", {"symbol_name": "hash"})
    assert out.index("hash_token_v2") > out.index("Complexity: 2")  # the exact match is listed first


# --- M5: a UTF-8 BOM doesn't hide a file's symbols ------------------------------

def test_file_with_bom_is_parsed(tmp_path):
    f = tmp_path / "bom.py"
    f.write_bytes(b"\xef\xbb\xbfdef f():\n    pass\n")
    assert [fn.name for fn in extract_file(f, 1).functions] == ["f"]


# --- M6: one bad MCP request can't stop the server ------------------------------

def test_mcp_server_survives_bad_requests(symbols_db, monkeypatch):
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "nope", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "repomind_search"}},
        "not json",
        [1, 2, 3],
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "repomind_search", "arguments": {"query": "alpha", "top_k": "abc"}}},
        {"jsonrpc": "2.0", "id": 4, "method": "ping"},
    ]
    lines = "".join((r if isinstance(r, str) else json.dumps(r)) + "\n" for r in requests)
    out = io.BytesIO()

    class FakeStdout:
        buffer = out

    monkeypatch.setattr(sys, "stdin", io.StringIO(lines))
    monkeypatch.setattr(sys, "stdout", FakeStdout())
    RepoMindMCPServer(db_path=symbols_db).run_stdio()

    replies = {r["id"]: r for r in map(json.loads, out.getvalue().decode().splitlines())}
    assert sorted(replies) == [1, 2, 3, 4]
    assert all(replies[i]["error"]["code"] == -32602 for i in (1, 2, 3))
    assert replies[4]["result"] == {}


def test_failing_tool_is_an_error_result(symbols_db, monkeypatch):
    server = RepoMindMCPServer(db_path=symbols_db)

    def boom(name, arguments):
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(server, "handle_tool_call", boom)
    res = server._call_tool(7, {"name": "repomind_health_summary", "arguments": {}})
    assert res["result"]["isError"] is True
    assert "disk on fire" in res["result"]["content"][0]["text"]


# --- M7: the benchmark samples every kind of question ---------------------------

def test_benchmark_sample_covers_all_kinds(tmp_path, symbols_db):
    gold = tmp_path / "gold.json"
    items = [{"q": f"n{i}", "expected": ["a.py"], "kind": "natural"} for i in range(20)]
    items += [{"q": f"i{i}", "expected": ["a.py"], "kind": "identifier"} for i in range(15)]
    gold.write_text(json.dumps(items), encoding="utf-8")
    evaluator = RetrievalEvaluator.__new__(RetrievalEvaluator)  # no models needed to load questions
    evaluator.db_path = symbols_db
    picked = [b["q"] for b in evaluator.load_benchmark(gold_path=gold, max_samples=12)]
    assert len(picked) == 12
    assert any(q.startswith("i") for q in picked) and any(q.startswith("n") for q in picked)


# --- M8: the CLI uses Groq when a key is set -------------------------------------

def test_cli_llm_follows_groq_key(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert isinstance(default_llm_client("phi3", "http://x"), OllamaClient)
    (tmp_path / ".env").write_text('GROQ_API_KEY="gsk_from_file"\n', encoding="utf-8")
    assert env_setting("GROQ_API_KEY") == "gsk_from_file"
    client_ = default_llm_client("phi3", "http://x")
    assert isinstance(client_, GroqClient) and client_.api_key == "gsk_from_file"


# --- M9: unknown things are reported, not quietly replaced -----------------------

def test_unknown_repo_id_is_404():
    res = client.get("/api/files/tree?repo_id=does_not_exist")
    assert res.status_code == 404
    assert "does_not_exist" in res.json()["detail"]
    assert client.get("/api/symbols?repo_id=does_not_exist").status_code == 404


def test_unknown_impact_target_is_not_found(symbols_db, tmp_path):
    builder = GraphBuilder(symbols_db, tmp_path)
    builder.build()
    assert builder.compute_blast_radius("zzz_nothing")["found"] is False
    result = CliRunner().invoke(cli_app, ["impact", "zzz_nothing", "--db", str(symbols_db), "--path", str(tmp_path)])
    assert result.exit_code == 1
    assert "No file or symbol called" in result.output
