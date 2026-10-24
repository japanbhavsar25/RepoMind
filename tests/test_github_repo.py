"""Tests for adding repositories from a GitHub link (clone is mocked, no network)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.config import settings
from backend.main import app
from backend.services.repo_manager import RepoManager, repo_manager

client = TestClient(app)


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch):
    """Point data storage at tmp_path and drop any repos registered during the test."""
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    before = set(repo_manager._registry)
    active = repo_manager._active_repo_id
    yield tmp_path
    for repo_id in set(repo_manager._registry) - before:
        del repo_manager._registry[repo_id]
    repo_manager._active_repo_id = active


def fake_clone(files: dict[str, str]):
    """Return a _git_clone replacement that writes `files` into the destination."""
    calls = []

    def _clone(self, url: str, dest: Path) -> None:
        calls.append(url)
        for rel, text in files.items():
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")

    _clone.calls = calls
    return _clone


def test_add_github_repo_clones_and_indexes(isolated, monkeypatch):
    clone = fake_clone({"pkg/app.py": "def hello():\n    return 1\n"})
    monkeypatch.setattr(RepoManager, "_git_clone", clone)

    res = client.post("/api/repos/github", json={"url": "https://github.com/Acme/Widgets"})
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Acme/Widgets"
    assert data["id"].startswith("gh_acme_widgets_")
    assert clone.calls == ["https://github.com/acme/widgets.git"]
    assert repo_manager.active_repo_id == data["id"]

    idx = client.post(f"/api/repos/index?repo_id={data['id']}")
    assert idx.status_code == 200
    assert idx.json()["files_indexed"] == 1
    assert idx.json()["functions_indexed"] == 1


def test_same_url_is_not_cloned_twice(isolated, monkeypatch):
    clone = fake_clone({"a.py": "x = 1\n"})
    monkeypatch.setattr(RepoManager, "_git_clone", clone)

    first = client.post("/api/repos/github", json={"url": "https://github.com/acme/widgets"})
    second = client.post("/api/repos/github", json={"url": "https://github.com/ACME/widgets.git"})
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert len(clone.calls) == 1


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/acme/widgets",  # not HTTPS
        "https://evil.example.com/acme/widgets",  # host not allowed
        "https://127.0.0.1/acme/widgets",  # local network
        "https://github.com/acme",  # missing repo name
        "https://github.com/acme/widgets;rm -rf /",  # injection attempt
    ],
)
def test_rejects_unsafe_or_malformed_urls(isolated, monkeypatch, url):
    clone = fake_clone({"a.py": "x = 1\n"})
    monkeypatch.setattr(RepoManager, "_git_clone", clone)

    res = client.post("/api/repos/github", json={"url": url})
    assert res.status_code == 400
    assert clone.calls == []


def test_repo_without_python_files_is_rejected_and_cleaned_up(isolated, monkeypatch):
    monkeypatch.setattr(RepoManager, "_git_clone", fake_clone({"README.md": "# hi\n"}))

    res = client.post("/api/repos/github", json={"url": "https://github.com/acme/docs-only"})
    assert res.status_code == 400
    assert "no Python files" in res.json()["detail"]
    assert not any((isolated / "clones").iterdir())


def test_repo_over_file_limit_is_rejected(isolated, monkeypatch):
    monkeypatch.setattr(settings, "max_repo_files", 2)
    files = {f"m{i}.py": "x = 1\n" for i in range(3)}
    monkeypatch.setattr(RepoManager, "_git_clone", fake_clone(files))

    res = client.post("/api/repos/github", json={"url": "https://github.com/acme/big"})
    assert res.status_code == 400
    assert "limit" in res.json()["detail"]


def test_clone_failure_returns_friendly_error(isolated, monkeypatch):
    def failing_clone(self, url, dest):
        raise ValueError("Could not clone the repository. Check the link is correct and the repo is public.")

    monkeypatch.setattr(RepoManager, "_git_clone", failing_clone)
    res = client.post("/api/repos/github", json={"url": "https://github.com/acme/private"})
    assert res.status_code == 400
    assert "public" in res.json()["detail"]


def test_clone_timeout_returns_504(isolated, monkeypatch):
    def slow_clone(self, url, dest):
        raise TimeoutError("Cloning took too long.")

    monkeypatch.setattr(RepoManager, "_git_clone", slow_clone)
    res = client.post("/api/repos/github", json={"url": "https://github.com/acme/huge"})
    assert res.status_code == 504


def test_oversized_files_are_skipped_during_indexing(isolated, monkeypatch):
    monkeypatch.setattr(settings, "max_file_size_bytes", 50)
    files = {"small.py": "x = 1\n", "big.py": "y = 2\n" * 50}
    monkeypatch.setattr(RepoManager, "_git_clone", fake_clone(files))

    repo_id = client.post("/api/repos/github", json={"url": "https://github.com/acme/mixed"}).json()["id"]
    idx = client.post(f"/api/repos/index?repo_id={repo_id}")
    assert idx.json()["files_indexed"] == 1
