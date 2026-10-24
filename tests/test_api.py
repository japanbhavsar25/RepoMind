"""Integration and contract tests for the RepoMind FastAPI backend."""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.repo_manager import repo_manager


@pytest.fixture(scope="module")
def client():
    # Ensure sample repo is indexed for testing
    repo_manager.index_repo("ecommerce_sample")
    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "fts5_enabled" in data


def test_list_repositories(client):
    res = client.get("/api/repos")
    assert res.status_code == 200
    data = res.json()
    assert "repos" in data
    assert "active_repo_id" in data
    assert len(data["repos"]) >= 1
    sample = next((r for r in data["repos"] if r["id"] == "ecommerce_sample"), None)
    assert sample is not None
    assert sample["is_sample"] is True


def test_select_repository(client):
    res = client.post("/api/repos/select", json={"repo_id": "ecommerce_sample"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["active_repo_id"] == "ecommerce_sample"


def test_select_unknown_repository(client):
    res = client.post("/api/repos/select", json={"repo_id": "non_existent_repo_123"})
    assert res.status_code == 404


def test_get_file_tree(client):
    res = client.get("/api/files/tree?repo_id=ecommerce_sample")
    assert res.status_code == 200
    data = res.json()
    assert "root" in data
    assert data["total_files"] >= 5
    assert data["root"]["type"] == "directory"


def test_get_file_content(client):
    res = client.get("/api/files/content?path=models.py&repo_id=ecommerce_sample")
    assert res.status_code == 200
    data = res.json()
    assert data["path"] == "models.py"
    assert data["line_count"] > 10
    assert "class User:" in data["content"]


def test_path_traversal_protection(client):
    # Attempt to escape repo boundary
    res = client.get("/api/files/content?path=../../pyproject.toml&repo_id=ecommerce_sample")
    assert res.status_code == 403
    assert "escapes repository boundary" in res.json()["detail"]


def test_list_symbols(client):
    res = client.get("/api/symbols?repo_id=ecommerce_sample")
    assert res.status_code == 200
    data = res.json()
    assert "symbols" in data
    assert data["total_count"] >= 10
    names = [s["name"] for s in data["symbols"]]
    assert "calculate_tax" in names
    assert "User" in names


def test_get_symbol_detail(client):
    res = client.get("/api/symbols/calculate_tax?repo_id=ecommerce_sample")
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "calculate_tax"
    assert data["file_path"] == "utils.py"
    assert "tax_rate" in data["source_code"]


def test_search_code(client):
    res = client.post("/api/search?repo_id=ecommerce_sample", json={"query": "calculate_tax", "top_k": 3})
    assert res.status_code == 200
    data = res.json()
    assert data["query"] == "calculate_tax"
    assert len(data["results"]) >= 1
    top_hit = data["results"][0]
    assert "utils.py" in top_hit["file_path"] or "calculate_tax" in top_hit["snippet"]


def test_grounded_qa_without_llm(client):
    res = client.post(
        "/api/ask?repo_id=ecommerce_sample",
        json={"question": "Where is calculate_tax implemented?", "top_k": 3, "use_llm": False},
    )
    assert res.status_code == 200
    data = res.json()
    assert "calculate_tax" in data["answer"] or len(data["citations"]) > 0
    assert data["chunks_retrieved"] >= 1


def test_graph_data(client):
    res = client.get("/api/graph?repo_id=ecommerce_sample")
    assert res.status_code == 200
    data = res.json()
    assert len(data["nodes"]) >= 5
    assert len(data["edges"]) >= 5
    assert "orphan_task.py" in data["orphans"]


def test_impact_analysis(client):
    res = client.get("/api/impact/models.py?repo_id=ecommerce_sample")
    assert res.status_code == 200
    data = res.json()
    assert data["target"] == "models.py"
    assert data["found"] is True
    # Downstream dependents should include orders.py or database.py
    assert len(data["direct_importers"]) >= 1


def test_evaluate_endpoint(client):
    res = client.get("/api/evaluate?repo_id=ecommerce_sample&max_samples=2")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "dense" in data
    assert "sparse" in data
    assert "hybrid" in data
