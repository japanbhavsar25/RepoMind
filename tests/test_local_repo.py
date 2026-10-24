"""Tests for custom local repository registration, persistence, and isolation."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.repo_manager import RepoManager, repo_manager


def test_register_local_repo_success(tmp_path: Path):
    # Create a small valid Python project
    sample_dir = tmp_path / "my_custom_service"
    sample_dir.mkdir()
    (sample_dir / "service.py").write_text(
        "def compute_total(a: int, b: int) -> int:\n    '''Compute total sum.'''\n    return a + b\n",
        encoding="utf-8",
    )

    client = TestClient(app)
    res = client.post(
        "/api/repos/local",
        json={"name": "My Custom Service", "path": str(sample_dir)},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "My Custom Service"
    assert "id" in data
    assert data["is_sample"] is False
    assert data["is_indexed"] is False

    repo_id = data["id"]

    # Verify isolated storage location
    managed = repo_manager.get_repo(repo_id)
    assert managed.db_path.parent.name == repo_id
    assert managed.chroma_dir.parent.name == repo_id
    assert "samples" not in str(managed.db_path)

    # Index the newly added repository
    idx_res = client.post(f"/api/repos/index?repo_id={repo_id}")
    assert idx_res.status_code == 200
    idx_data = idx_res.json()
    assert idx_data["files_indexed"] == 1
    assert idx_data["functions_indexed"] == 1

    # Verify symbol retrieval works on custom repo
    sym_res = client.get(f"/api/symbols?repo_id={repo_id}")
    assert sym_res.status_code == 200
    sym_data = sym_res.json()
    assert sym_data["total_count"] == 1
    assert sym_data["symbols"][0]["name"] == "compute_total"


def test_register_duplicate_repo_rejected(tmp_path: Path):
    sample_dir = tmp_path / "dup_service"
    sample_dir.mkdir()

    client = TestClient(app)
    res1 = client.post(
        "/api/repos/local",
        json={"name": "Service One", "path": str(sample_dir)},
    )
    assert res1.status_code == 201

    # Attempting to register the same directory again should yield 409 Conflict
    res2 = client.post(
        "/api/repos/local",
        json={"name": "Service Two", "path": str(sample_dir)},
    )
    assert res2.status_code == 409
    assert "already registered" in res2.json()["detail"].lower()


def test_register_nonexistent_path_rejected():
    client = TestClient(app)
    fake_path = "D:\\ThisFolderDoesNotExistAtAll_123456789"
    res = client.post(
        "/api/repos/local",
        json={"name": "Fake Repo", "path": fake_path},
    )
    assert res.status_code == 400
    assert "does not exist" in res.json()["detail"].lower()


def test_register_file_path_rejected(tmp_path: Path):
    file_path = tmp_path / "some_file.py"
    file_path.write_text("x = 1\n", encoding="utf-8")

    client = TestClient(app)
    res = client.post(
        "/api/repos/local",
        json={"name": "File Repo", "path": str(file_path)},
    )
    assert res.status_code == 400
    assert "not a directory" in res.json()["detail"].lower()


def test_register_empty_fields_rejected():
    client = TestClient(app)
    res = client.post(
        "/api/repos/local",
        json={"name": "   ", "path": "   "},
    )
    assert res.status_code == 422  # Pydantic validation error


def test_persistence_across_restarts(tmp_path: Path):
    sample_dir = tmp_path / "persistent_service"
    sample_dir.mkdir()

    client = TestClient(app)
    res = client.post(
        "/api/repos/local",
        json={"name": "Persistent Service", "path": str(sample_dir)},
    )
    assert res.status_code == 201
    repo_id = res.json()["id"]

    # Verify custom_repos.json contains the entry
    custom_repos_file = repo_manager.custom_repos_file
    assert custom_repos_file.exists()
    content = json.loads(custom_repos_file.read_text(encoding="utf-8"))
    ids = [item["id"] for item in content]
    assert repo_id in ids

    # Create a fresh RepoManager instance (simulating restart)
    fresh_manager = RepoManager()
    assert repo_id in fresh_manager._registry
    restored = fresh_manager.get_repo(repo_id)
    assert restored.name == "Persistent Service"
    assert restored.root_path == sample_dir.resolve()


def test_isolated_storage_between_repositories(tmp_path: Path):
    # Setup Repo A
    dir_a = tmp_path / "repo_alpha"
    dir_a.mkdir()
    (dir_a / "alpha.py").write_text("def run_alpha():\n    return 42\n", encoding="utf-8")

    # Setup Repo B
    dir_b = tmp_path / "repo_beta"
    dir_b.mkdir()
    (dir_b / "beta.py").write_text("def run_beta():\n    return 99\n", encoding="utf-8")

    client = TestClient(app)
    res_a = client.post("/api/repos/local", json={"name": "Repo Alpha", "path": str(dir_a)})
    assert res_a.status_code == 201
    id_a = res_a.json()["id"]

    res_b = client.post("/api/repos/local", json={"name": "Repo Beta", "path": str(dir_b)})
    assert res_b.status_code == 201
    id_b = res_b.json()["id"]

    repo_a = repo_manager.get_repo(id_a)
    repo_b = repo_manager.get_repo(id_b)

    # Verify completely isolated database paths
    assert repo_a.db_path != repo_b.db_path
    assert repo_a.chroma_dir != repo_b.chroma_dir
    assert repo_a.db_path.parent != repo_b.db_path.parent

    # Index both
    assert client.post(f"/api/repos/index?repo_id={id_a}").status_code == 200
    assert client.post(f"/api/repos/index?repo_id={id_b}").status_code == 200

    # Verify symbol isolation
    syms_a = client.get(f"/api/symbols?repo_id={id_a}").json()["symbols"]
    syms_b = client.get(f"/api/symbols?repo_id={id_b}").json()["symbols"]

    names_a = [s["name"] for s in syms_a]
    names_b = [s["name"] for s in syms_b]

    assert "run_alpha" in names_a
    assert "run_beta" not in names_a

    assert "run_beta" in names_b
    assert "run_alpha" not in names_b


def test_indexing_failure_on_deleted_folder(tmp_path: Path):
    import shutil

    del_dir = tmp_path / "to_be_deleted"
    del_dir.mkdir()
    (del_dir / "mod.py").write_text("x = 1\n", encoding="utf-8")

    client = TestClient(app)
    res = client.post("/api/repos/local", json={"name": "Doomed Repo", "path": str(del_dir)})
    assert res.status_code == 201
    repo_id = res.json()["id"]

    # Delete the directory on disk
    shutil.rmtree(del_dir)

    # Attempt to index deleted directory
    idx_res = client.post(f"/api/repos/index?repo_id={repo_id}")
    assert idx_res.status_code in (400, 404, 500)
    assert "does not exist" in idx_res.json()["detail"].lower()


def test_null_byte_path_rejected():
    client = TestClient(app)
    res = client.post(
        "/api/repos/local",
        json={"name": "Null Repo", "path": "D:\\safe_dir\0\\malicious"},
    )
    assert res.status_code in (400, 422)
