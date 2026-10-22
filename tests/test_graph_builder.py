# tests/test_graph_builder.py
"""Tests for the dependency graph builder."""

from pathlib import Path

from repomind.database import ImportRecord, RepoDatabase
from repomind.graph_builder import GraphBuilder, _module_name_for_path


def _make_db(tmp_path: Path, files: dict[str, str], imports: list[ImportRecord]) -> Path:
    """Create a database with the given files (contents unused) and imports.

    Files are inserted in dict order, so file ids are 1, 2, ... — tests
    reference them by that order.
    """
    db_path = tmp_path / "test.db"
    with RepoDatabase(db_path) as db:
        for rel_path in files:
            db.insert_file(rel_path, "hash", 1, 0.0)
        db.insert_imports(imports)
        db.commit()
    return db_path


def _edges(graph):
    return {
        (src, dst, data.get("type"))
        for src, dst, data in graph.edges(data=True)
    }


def test_module_name_for_path():
    assert _module_name_for_path("pkg/sub/mod.py") == "pkg.sub.mod"
    assert _module_name_for_path("pkg/__init__.py") == "pkg"
    assert _module_name_for_path("pkg/sub/__init__.py") == "pkg.sub"
    assert _module_name_for_path("pkg/name.python.py") == "pkg.name.python"


def test_internal_edge_from_absolute_import(tmp_path):
    imports = [
        ImportRecord(1, "pkg.utils", None, False, 1),
    ]
    db_path = _make_db(tmp_path, {"pkg/cli.py": "", "pkg/utils.py": ""}, imports)

    builder = GraphBuilder(db_path, tmp_path)
    builder.build()

    assert ("pkg/cli.py", "pkg/utils.py", "internal") in _edges(builder.graph)


def test_from_import_resolves_submodule(tmp_path):
    """'from pkg import database' should link cli.py to database.py."""
    imports = [
        ImportRecord(3, "pkg", "database", True, 1),
    ]
    db_path = _make_db(
        tmp_path,
        {"pkg/__init__.py": "", "pkg/database.py": "", "pkg/cli.py": ""},
        imports,
    )

    builder = GraphBuilder(db_path, tmp_path)
    builder.build()

    edges = _edges(builder.graph)
    assert ("pkg/cli.py", "pkg/database.py", "internal") in edges


def test_third_party_becomes_external_node(tmp_path):
    imports = [ImportRecord(1, "requests", None, False, 1)]
    db_path = _make_db(tmp_path, {"app.py": ""}, imports)

    builder = GraphBuilder(db_path, tmp_path)
    builder.build()

    assert ("app.py", "ext:requests", "external") in _edges(builder.graph)


def test_stdlib_imports_are_skipped(tmp_path):
    imports = [ImportRecord(1, "os.path", None, False, 1)]
    db_path = _make_db(tmp_path, {"app.py": ""}, imports)

    builder = GraphBuilder(db_path, tmp_path)
    builder.build()

    assert builder.graph.number_of_edges() == 0
    assert "ext:os.path" not in builder.graph


def test_self_import_creates_no_edge(tmp_path):
    imports = [ImportRecord(1, "app", None, False, 1)]
    db_path = _make_db(tmp_path, {"app.py": ""}, imports)

    builder = GraphBuilder(db_path, tmp_path)
    builder.build()

    assert builder.graph.number_of_edges() == 0


def test_analyze_empty_graph_has_consistent_shape(tmp_path):
    db_path = _make_db(tmp_path, {}, [])
    builder = GraphBuilder(db_path, tmp_path)
    builder.build()

    analysis = builder.analyze()
    assert analysis == {
        "node_count": 0,
        "edge_count": 0,
        "pagerank": {},
        "orphans": [],
        "cycles": [],
    }


def test_analyze_finds_orphans_and_pagerank(tmp_path):
    # b imports a; c is connected to nobody
    imports = [ImportRecord(2, "a", None, False, 1)]
    db_path = _make_db(tmp_path, {"a.py": "", "b.py": "", "c.py": ""}, imports)

    builder = GraphBuilder(db_path, tmp_path)
    builder.build()
    analysis = builder.analyze()

    assert analysis["node_count"] == 3
    assert analysis["edge_count"] == 1
    assert set(analysis["orphans"]) == {"c.py"}
    assert analysis["pagerank"]


def test_analyze_finds_cycles(tmp_path):
    imports = [
        ImportRecord(1, "b", None, False, 1),
        ImportRecord(2, "a", None, False, 1),
    ]
    db_path = _make_db(tmp_path, {"a.py": "", "b.py": ""}, imports)

    builder = GraphBuilder(db_path, tmp_path)
    builder.build()
    analysis = builder.analyze()

    assert len(analysis["cycles"]) == 1
    assert set(analysis["cycles"][0]) == {"a.py", "b.py"}


def test_to_pyvis_generates_self_contained_html(tmp_path):
    imports = [ImportRecord(2, "a", None, False, 1)]
    db_path = _make_db(tmp_path, {"a.py": "", "b.py": ""}, imports)

    builder = GraphBuilder(db_path, tmp_path)
    builder.build()
    net = builder.to_pyvis()
    out = tmp_path / "graph.html"
    net.save_graph(str(out))

    html = out.read_text(encoding="utf-8")
    # in_line mode embeds the vis.js source instead of linking a lib/ folder
    assert "lib/bindings/utils.js" not in html
    assert len(html) > 100_000  # libraries really are embedded
