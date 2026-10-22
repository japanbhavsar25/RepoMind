# tests/test_cli.py
"""Tests for the Typer CLI."""

import pytest
from typer.testing import CliRunner

from repomind.cli import app
from repomind.database import FunctionRecord, RepoDatabase

runner = CliRunner()


@pytest.fixture()
def indexed_db(tmp_path):
    """A minimal indexed database in a temp directory."""
    db_path = tmp_path / "test.db"
    with RepoDatabase(db_path) as db:
        file_id = db.insert_file("src/auth.py", "hash1", 10, 0.0)
        db.insert_functions(
            [
                FunctionRecord(
                    file_id, "authenticate_user", "authenticate_user", 1, 5, None, "def x(): pass"
                )
            ]
        )
        db.commit()
    return db_path


def test_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "RepoMind" in result.output


def test_stats_shows_counts(indexed_db):
    result = runner.invoke(app, ["stats", "--db", str(indexed_db)])
    assert result.exit_code == 0
    assert "Files" in result.output


def test_search_finds_function(indexed_db):
    result = runner.invoke(app, ["search", "authenticate", "--db", str(indexed_db)])
    assert result.exit_code == 0
    assert "authenticate_user" in result.output


def test_search_without_results(indexed_db):
    result = runner.invoke(app, ["search", "no_such_symbol", "--db", str(indexed_db)])
    assert result.exit_code == 0
    assert "No results" in result.output


def test_commands_fail_without_database(tmp_path):
    missing = tmp_path / "missing.db"
    result = runner.invoke(app, ["stats", "--db", str(missing)])
    assert result.exit_code == 1
    assert "No database found" in result.output


def test_index_creates_database(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "hello.py").write_text('def greet(name):\n    """Greet."""\n    return name\n')
    db_path = tmp_path / "out.db"

    result = runner.invoke(app, ["index", str(project), "--db", str(db_path)])
    assert result.exit_code == 0, result.output

    with RepoDatabase(db_path) as db:
        stats = db.get_stats()
    assert stats["files"] == 1
    assert stats["functions"] == 1


def test_index_skips_unchanged_files(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "hello.py").write_text("def greet():\n    pass\n")
    db_path = tmp_path / "out.db"

    first = runner.invoke(app, ["index", str(project), "--db", str(db_path)])
    second = runner.invoke(app, ["index", str(project), "--db", str(db_path)])

    assert first.exit_code == 0 and second.exit_code == 0
    assert "unchanged file(s) skipped" in second.output

    # Symbols must not be duplicated by the second run
    with RepoDatabase(db_path) as db:
        assert db.get_stats()["functions"] == 1


def test_index_prunes_deleted_files(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    target = project / "hello.py"
    target.write_text("def greet():\n    pass\n")
    db_path = tmp_path / "out.db"

    runner.invoke(app, ["index", str(project), "--db", str(db_path)])
    target.unlink()
    result = runner.invoke(app, ["index", str(project), "--db", str(db_path)])

    assert result.exit_code == 0
    assert "removed from index" in result.output
    with RepoDatabase(db_path) as db:
        assert db.get_stats()["files"] == 0
