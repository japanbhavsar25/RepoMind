"""Regression tests for the QA report's Low and Nit findings."""

import pytest
from fastapi.testclient import TestClient

from backend.config import settings
from backend.main import app
from backend.services import search_service as search_module
from backend.services.repo_manager import IndexingInProgressError, repo_manager
from repomind.database import CallRecord, FunctionRecord, RepoDatabase
from repomind.parser import extract_file
from repomind.report import architecture_health_score

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def indexed_sample():
    repo_manager.index_repo("ecommerce_sample")


# --- L1: no internals in error responses -----------------------------------------

def test_500_hides_the_exception_text(monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("sqlite failed at /srv/secret/path.db")

    monkeypatch.setattr(search_module.search_service, "execute_search", boom)
    res = client.post("/api/search?repo_id=ecommerce_sample", json={"query": "x"})
    assert res.status_code == 500
    assert "secret" not in res.text
    assert res.json()["detail"].startswith("Search failed on the server")


def test_public_mode_hides_server_paths(monkeypatch):
    monkeypatch.setattr(settings, "public_mode", True)
    assert client.get("/api/health").json()["data_dir"] == ""
    assert all(r["path"] == "" for r in client.get("/api/repos").json()["repos"])


# --- L4: search numbers and the keyword fallback --------------------------------

class FakeRAG:
    """Stands in for RepoRAG: a fixed vector index (or none), no models."""

    chunks = 0

    def __init__(self, db_path):
        self.collection = type("C", (), {"count": staticmethod(lambda: FakeRAG.chunks)})()

    def retrieve(self, query, top_k, hybrid, rerank):
        metas = [{"file": f"m{i}.py", "start": 1, "end": 2, "kind": "func"} for i in range(3)]
        return ["code"] * 3, metas, ["func_1", "func_2", "func_3"]


@pytest.fixture
def fts_repo(tmp_path, monkeypatch):
    """A repo whose database has one function and its keyword-index row."""
    db_path = tmp_path / "fts.db"
    with RepoDatabase(db_path) as db:
        fid = db.insert_file("shop/auth.py", "h", 20, 0.0)
        db.insert_functions([FunctionRecord(fid, "hash_password", "hash_password", 4, 9, None, "def hash_password(): ...")])
        row_id = db.get_all_symbols()[0][1]
        db.insert_fts_chunks([(f"func_{row_id}", "shop/auth.py", "hash_password", "def hash_password(): ...")])
        db.commit()
    monkeypatch.setattr(search_module, "RepoRAG", FakeRAG)
    monkeypatch.setattr(search_module.repo_manager, "get_repo", lambda repo_id=None: type("R", (), {"db_path": db_path})())


def test_hybrid_scores_are_reciprocal_ranks(fts_repo, monkeypatch):
    monkeypatch.setattr(FakeRAG, "chunks", 3)
    res = search_module.search_service.execute_search(repo_id=None, query="hash a password", top_k=3)
    assert [r["score"] for r in res["results"]] == [1.0, 0.5, 0.3333]


def test_keyword_fallback_returns_real_files_and_lines(fts_repo):
    res = search_module.search_service.execute_search(repo_id=None, query="hash_password", top_k=3)
    [hit] = res["results"]
    assert hit["match_type"] == "fts5_sparse"
    assert (hit["file_path"], hit["line_start"], hit["line_end"]) == ("shop/auth.py", 4, 9)


# --- L5: evidence-only text says why ---------------------------------------------

def test_evidence_only_explains_itself():
    answer = client.post(
        "/api/ask?repo_id=ecommerce_sample", json={"question": "Where is password hashing?", "use_llm": False}
    ).json()["answer"]
    assert "You turned off written answers" in answer
    assert "###" not in answer


# --- L6: one index run per repo at a time -----------------------------------------

def test_second_index_of_the_same_repo_is_refused():
    repo_manager.index_repo("ecommerce_sample")  # creates the repo's lock
    lock = repo_manager._index_locks["ecommerce_sample"]
    lock.acquire()
    try:
        with pytest.raises(IndexingInProgressError):
            repo_manager.index_repo("ecommerce_sample")
        assert client.post("/api/repos/index?repo_id=ecommerce_sample").status_code == 409
    finally:
        lock.release()


# --- L8: one health formula ------------------------------------------------------

def test_health_score_counts_ghost_files_and_caps():
    hot = [{"risk_level": "CRITICAL", "bus_factor_risk": True}] * 30
    assert architecture_health_score(0, 0, [], 0) == 100
    assert architecture_health_score(0, 0, [], 4) == 96  # ghost files cost a point each
    assert architecture_health_score(5, 50, hot, 50) == 10  # every penalty capped, floor of 10


# --- N1: % and _ are literal in name searches ------------------------------------

def test_like_wildcards_are_literal(tmp_path):
    with RepoDatabase(tmp_path / "n1.db") as db:
        fid = db.insert_file("a.py", "h", 1, 0.0)
        db.insert_functions([
            FunctionRecord(fid, "hash_token", "hash_token", 1, 2, None, ""),
            FunctionRecord(fid, "hashXtoken", "hashXtoken", 3, 4, None, ""),
        ])
        db.insert_symbol_calls([
            CallRecord(fid, "a.py", "f", "x.hashXtoken", 5),
            CallRecord(fid, "a.py", "g", "x.hash_token", 6),
        ])
        db.commit()
        assert db.search("%") == []
        assert [r[1] for r in db.search("a_h")] == []  # as a wildcard, _ would match "ash"
        assert [r[1] for r in db.search("hash_token")] == ["hash_token"]
        assert [r[2] for r in db.get_symbol_calls(callee_name="hash_token")] == ["x.hash_token"]


# --- N4: decorators are part of a symbol's lines -----------------------------------

def test_decorators_are_inside_the_line_range(tmp_path):
    f = tmp_path / "routes.py"
    f.write_text("import functools\n\n@functools.cache\n@staticmethod\ndef handler():\n    return 1\n", encoding="utf-8")
    fn = extract_file(f, 1).functions[0]
    assert (fn.line_start, fn.line_end) == (3, 6)
    assert fn.source_code.startswith("@functools.cache")
