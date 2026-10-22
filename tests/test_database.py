# tests/test_database.py
"""Tests for the SQLite storage layer."""

import pytest

from repomind.database import (
    ClassRecord,
    FunctionRecord,
    ImportRecord,
    RepoDatabase,
)


@pytest.fixture()
def db(tmp_path):
    with RepoDatabase(tmp_path / "test.db") as conn:
        yield conn


def _sample_records(file_id: int):
    return (
        [
            FunctionRecord(file_id, "run", "run", 1, 3, "Doc.", "def run():\n    pass\n"),
        ],
        [
            ClassRecord(file_id, "App", "App", 5, 9, None, "class App:\n    pass\n"),
        ],
        [
            ImportRecord(file_id, "os", "os", False, 1),
            ImportRecord(file_id, "pkg.mod", "helper", True, 2),
        ],
    )


def test_insert_and_stats(db):
    file_id = db.insert_file("a.py", "hash1", 10, 0.0)
    funcs, classes, imports = _sample_records(file_id)
    db.insert_functions(funcs)
    db.insert_classes(classes)
    db.insert_imports(imports)
    db.commit()

    stats = db.get_stats()
    assert stats == {"files": 1, "functions": 1, "classes": 1, "imports": 2}


def test_insert_file_upserts_on_same_path(db):
    first = db.insert_file("a.py", "hash1", 10, 0.0)
    second = db.insert_file("a.py", "hash2", 12, 1.0)
    db.commit()

    assert first == second  # same row updated, not duplicated
    assert db.get_stats()["files"] == 1


def test_deleting_file_cascades_to_symbols(db):
    file_id = db.insert_file("a.py", "hash1", 10, 0.0)
    funcs, classes, imports = _sample_records(file_id)
    db.insert_functions(funcs)
    db.insert_classes(classes)
    db.insert_imports(imports)
    db.commit()

    # Removing the file row must remove its symbols via ON DELETE CASCADE
    db.prune_paths(set())
    db.commit()

    assert db.get_stats() == {"files": 0, "functions": 0, "classes": 0, "imports": 0}


def test_delete_symbols_keeps_file_row(db):
    file_id = db.insert_file("a.py", "hash1", 10, 0.0)
    funcs, classes, imports = _sample_records(file_id)
    db.insert_functions(funcs)
    db.insert_classes(classes)
    db.insert_imports(imports)
    db.commit()

    db.delete_symbols(file_id)
    db.commit()

    assert db.get_stats() == {"files": 1, "functions": 0, "classes": 0, "imports": 0}


def test_clear_removes_everything(db):
    file_id = db.insert_file("a.py", "hash1", 10, 0.0)
    funcs, classes, imports = _sample_records(file_id)
    db.insert_functions(funcs)
    db.insert_classes(classes)
    db.insert_imports(imports)
    db.commit()

    db.clear()
    db.commit()

    assert db.get_stats() == {"files": 0, "functions": 0, "classes": 0, "imports": 0}


def test_prune_paths_removes_stale_files(db):
    id_a = db.insert_file("a.py", "hash1", 10, 0.0)
    db.insert_file("b.py", "hash2", 5, 0.0)
    funcs, classes, imports = _sample_records(id_a)
    db.insert_functions(funcs)
    db.insert_classes(classes)
    db.insert_imports(imports)
    db.commit()

    removed = db.prune_paths({"b.py"})
    db.commit()

    assert removed == 1
    assert db.get_stats() == {"files": 1, "functions": 0, "classes": 0, "imports": 0}


def test_search_finds_by_name_and_qualified_name(db):
    file_id = db.insert_file("src/a.py", "hash1", 10, 0.0)
    db.insert_functions(
        [
            FunctionRecord(file_id, "authenticate_user", "authenticate_user", 1, 5, None, "x"),
            FunctionRecord(file_id, "run", "App.run", 7, 9, None, "x"),
        ]
    )
    db.commit()

    assert len(db.search("authenticate")) == 1
    assert len(db.search("app.run")) == 1
    assert db.search("missing_thing") == []


def test_get_all_symbols_joins_file_path(db):
    file_id = db.insert_file("src/a.py", "hash1", 10, 0.0)
    funcs, classes, _ = _sample_records(file_id)
    db.insert_functions(funcs)
    db.insert_classes(classes)
    db.commit()

    symbols = db.get_all_symbols()
    kinds = {kind for kind, *_ in symbols}
    paths = {row[-1] for row in symbols}
    assert kinds == {"func", "class"}
    assert paths == {"src/a.py"}


def test_requires_context_manager():
    db = RepoDatabase("unused.db")
    with pytest.raises(RuntimeError):
        db.get_stats()
