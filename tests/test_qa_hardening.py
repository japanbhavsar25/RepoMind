"""Regression tests for the QA report's Critical and High findings (C1, H2-H6)."""

import sys
from urllib.parse import quote

import networkx as nx
import pytest
from fastapi.testclient import TestClient

from backend.config import settings
from backend.main import app
from backend.routers import impact as impact_router
from backend.services.repo_manager import repo_manager
from repomind.database import RepoDatabase
from repomind.graph_builder import pagerank
from repomind.llm import GroqClient
from repomind.rag import verify_citations

EVIL = {"Origin": "https://evil.example"}


@pytest.fixture(scope="module")
def client():
    repo_manager.index_repo("ecommerce_sample")
    with TestClient(app) as c:
        yield c


# --- C1: no cross-site reads, no dot-files ----------------------------------

def test_foreign_origin_gets_no_cors_grant(client):
    res = client.get("/api/files/content?repo_id=ecommerce_sample&path=models.py", headers=EVIL)
    assert "access-control-allow-origin" not in res.headers
    ok = client.get(
        "/api/files/content?repo_id=ecommerce_sample&path=models.py",
        headers={"Origin": "https://repo-mind-steel.vercel.app"},
    )
    assert ok.headers.get("access-control-allow-origin") == "https://repo-mind-steel.vercel.app"


@pytest.mark.parametrize("path", [".env", "sub/.env", ".git/config", "README.md", "data.db", "id_rsa"])
def test_only_python_source_is_served(client, path):
    assert client.get(f"/api/files/content?repo_id=ecommerce_sample&path={quote(path)}").status_code == 403


def test_tree_lists_only_python_files(client):
    def walk(node):
        yield node
        for child in node.get("children") or []:
            yield from walk(child)

    tree = client.get("/api/files/tree?repo_id=ecommerce_sample").json()
    files = [n["path"] for n in walk(tree["root"]) if n["type"] == "file"]
    assert files and all(f.endswith(".py") for f in files)
    assert tree["total_files"] == len(files)


def test_foreign_origin_cannot_register_or_index(client, tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    assert client.post("/api/repos/local", json={"name": "x", "path": str(tmp_path)}, headers=EVIL).status_code == 403
    assert client.post("/api/repos/index?repo_id=ecommerce_sample", headers=EVIL).status_code == 403


# --- H2: PageRank without SciPy ---------------------------------------------

def test_pagerank_matches_networkx_and_needs_no_scipy(monkeypatch):
    g = nx.gnp_random_graph(30, 0.1, seed=7, directed=True)
    expected = nx.pagerank(g)
    monkeypatch.setitem(sys.modules, "scipy", None)  # import scipy now fails, as on the slim install
    got = pagerank(g)
    assert max(abs(got[n] - expected[n]) for n in g) < 1e-6
    assert pagerank(nx.DiGraph()) == {}


# --- H3: file paths with folders reach the impact route -----------------------

def test_impact_accepts_paths_with_slashes(client, monkeypatch):
    seen = {}

    def fake_impact(target, repo_id=None):
        seen["target"] = target
        return {"target": target, "found": True, "kind": "file", "direct_importers": [],
                "transitive_dependents": [], "pagerank": 0.0, "complexity": 1, "callers": [], "limitations": []}

    monkeypatch.setattr(impact_router.graph_service, "compute_impact", fake_impact)
    res = client.get("/api/impact/" + quote("samples/ecommerce_service/models.py", safe=""))
    assert res.status_code == 200
    assert seen["target"] == "samples/ecommerce_service/models.py"


# --- H4: no made-up confidence ----------------------------------------------

def test_evidence_only_answer_has_no_confidence(client):
    res = client.post(
        "/api/ask?repo_id=ecommerce_sample",
        json={"question": "Where is calculate_tax implemented?", "use_llm": False},
    )
    assert res.status_code == 200
    assert res.json()["citation_confidence"] is None


def test_llm_failure_is_an_error_not_an_answer(client, monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "auto")
    monkeypatch.setattr(settings, "groq_api_key", "gsk_test")
    monkeypatch.setattr(GroqClient, "is_alive", lambda self: True)

    def boom(self, prompt, system=None, temperature=0.3):
        raise RuntimeError("Groq rejected the API key")

    monkeypatch.setattr(GroqClient, "generate", boom)
    res = client.post("/api/ask?repo_id=ecommerce_sample", json={"question": "Where is calculate_tax implemented?"})
    assert res.status_code == 502
    assert "Groq rejected the API key" in res.json()["detail"]


# --- H5: the verifier can't be fooled -----------------------------------------

@pytest.fixture()
def cite_db(tmp_path):
    db_file = tmp_path / "cite.db"
    with RepoDatabase(db_file) as db:
        db.insert_file("pkg/rag.py", "h1", 100, 0.0)
        db.insert_file("pkg/data.py", "h2", 100, 0.0)
        db.commit()
    return db_file


SHOWN = [{"file": "pkg/rag.py", "start": 10, "end": 20}]


@pytest.mark.parametrize(
    ("answer", "status"),
    [
        ("[pkg/rag.py:12-18]", "GROUNDED"),
        ("[rag.py:12-18]", "GROUNDED"),  # short name resolves on a path boundary
        ("[pkg/rag.py:900-950]", "NOT_GROUNDED"),  # lines that don't exist / weren't shown
        ("[pkg/rag.py:1-40]", "NOT_GROUNDED"),  # whole-file range
        ("[pkg/rag.py:18-12]", "INVALID_LINES"),
        ("[a.py:1-2]", "FILE_NOT_FOUND"),  # no longer matches pkg/data.py
    ],
)
def test_citation_statuses(cite_db, answer, status):
    report = verify_citations(answer, SHOWN, cite_db)
    assert [c["status"] for c in report["citations"]] == [status]
    assert report["confidence_score"] == (1.0 if status == "GROUNDED" else 0.0)


def test_duplicate_citations_count_once(cite_db):
    report = verify_citations("[pkg/rag.py:12-13] [pkg/rag.py:12-13] [pkg/rag.py:12-13] [nope.py:1-2]", SHOWN, cite_db)
    assert report["total_citations"] == 2
    assert report["confidence_score"] == 0.5


def test_no_citations_means_no_score(cite_db):
    report = verify_citations("No citations here.", SHOWN, cite_db)
    assert report["confidence_score"] is None
    assert report["level"] == "NONE"


# --- H6: no re-indexing the public demo ---------------------------------------

def test_public_mode_refuses_reindex_of_indexed_repo(client, monkeypatch):
    monkeypatch.setattr(settings, "public_mode", True)
    res = client.post("/api/repos/index?repo_id=ecommerce_sample")
    assert res.status_code == 403
