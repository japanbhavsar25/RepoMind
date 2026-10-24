"""Tests for public deployment mode (folder access disabled, GitHub clones rate-limited)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.config import settings
from backend.main import app
from backend.routers import repos as repos_router
from backend.services.repo_manager import RepoManager, repo_manager

client = TestClient(app)


@pytest.fixture
def public(monkeypatch):
    monkeypatch.setattr(settings, "public_mode", True)
    monkeypatch.setattr(repos_router, "_github_adds", repos_router.defaultdict(repos_router.deque))
    before = set(repo_manager._registry)
    active = repo_manager._active_repo_id
    yield
    for repo_id in set(repo_manager._registry) - before:
        del repo_manager._registry[repo_id]
    repo_manager._active_repo_id = active


def test_health_reports_local_repos_disabled(public):
    assert client.get("/api/health").json()["local_repos_enabled"] is False


def test_local_folder_registration_is_blocked(public, tmp_path: Path):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    res = client.post("/api/repos/local", json={"name": "Server Secrets", "path": str(tmp_path)})
    assert res.status_code == 403


def test_folder_picker_is_blocked(public):
    assert client.post("/api/repos/browse", json={}).status_code == 403


def test_github_adds_are_rate_limited_per_ip(public, monkeypatch):
    monkeypatch.setattr(settings, "github_adds_per_hour", 2)

    def fake_clone(self, url, dest):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "a.py").write_text("x = 1\n", encoding="utf-8")

    monkeypatch.setattr(RepoManager, "_git_clone", fake_clone)
    ip_a = {"X-Forwarded-For": "203.0.113.5"}
    ip_b = {"X-Forwarded-For": "198.51.100.7"}

    for name in ("one", "two"):
        res = client.post("/api/repos/github", json={"url": f"https://github.com/acme/{name}"}, headers=ip_a)
        assert res.status_code == 201
    blocked = client.post("/api/repos/github", json={"url": "https://github.com/acme/three"}, headers=ip_a)
    assert blocked.status_code == 429

    other = client.post("/api/repos/github", json={"url": "https://github.com/acme/four"}, headers=ip_b)
    assert other.status_code == 201


def test_private_mode_has_no_rate_limit(monkeypatch):
    monkeypatch.setattr(settings, "public_mode", False)
    assert client.get("/api/health").json()["local_repos_enabled"] is True


def test_models_are_cached_across_instances(monkeypatch):
    from repomind import embedder

    loads = []

    class FakeModel:
        def encode(self, texts, show_progress_bar=False):
            import numpy as np

            return np.zeros((len(texts), 3))

    def fake_st(name):
        loads.append(name)
        return FakeModel()

    monkeypatch.setattr(embedder, "_MODEL_CACHE", {})
    monkeypatch.setattr("sentence_transformers.SentenceTransformer", fake_st)
    embedder.CodeEmbedder("fake-model").embed_texts(["a"])
    embedder.CodeEmbedder("fake-model").embed_texts(["b"])
    assert loads == ["fake-model"]
