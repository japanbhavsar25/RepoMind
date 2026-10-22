"""Comprehensive unit and integration tests for RepoMind v2.0 flagship features."""

from __future__ import annotations

from repomind.database import CallRecord, FunctionRecord, RepoDatabase
from repomind.git_analyzer import GitAnalyzer
from repomind.graph_builder import GraphBuilder
from repomind.hybrid import CrossEncoderReranker, detect_query_intent, rrf_fuse, tokenize_code
from repomind.mcp_server import RepoMindMCPServer
from repomind.parser import PythonExtractor, extract_file
from repomind.rag import RepoRAG, verify_citations
from repomind.utils import split_identifier


def test_split_identifier_camel_and_snake():
    assert split_identifier("parseASTNode") == ["parse", "ast", "node"]
    assert split_identifier("ASTParser") == ["ast", "parser"]
    assert split_identifier("get_file_hashes") == ["get", "file", "hashes"]
    assert split_identifier("SCREAMING_SNAKE_CASE") == ["screaming", "snake", "case"]
    assert split_identifier("all_MiniLM_L6_v2") == ["all", "mini", "lm", "l", "6", "v", "2"]


def test_tokenize_code_preserves_composites_and_strips_stopwords():
    code = "def parseASTNode(self, raw_data): return raw_data.strip()"
    tokens = tokenize_code(code)
    # Stopwords like 'def', 'self', 'return' should be filtered
    assert "def" not in tokens
    assert "self" not in tokens
    assert "return" not in tokens
    # Composites and subtokens should be present
    assert "parseastnode" in tokens
    assert "parse" in tokens
    assert "ast" in tokens
    assert "node" in tokens
    assert "raw_data" in tokens
    assert "strip" in tokens


def test_query_intent_detection():
    # Identifier queries get boosted sparse weight
    q1 = detect_query_intent("how does parseASTNode work?")
    assert q1["sparse"] > q1["dense"]

    q2 = detect_query_intent("find auth_user in database.py")
    assert q2["sparse"] > q2["dense"]

    # Natural language queries have balanced weights
    q3 = detect_query_intent("how do I configure local settings")
    assert q3["dense"] == 1.0 and q3["sparse"] == 1.0


def test_weighted_rrf_fuse():
    list1 = ["doc_a", "doc_b"]
    list2 = ["doc_b", "doc_a"]
    # With equal weights, doc_a and doc_b get same score
    scores_equal = rrf_fuse([list1, list2], k=60, weights=[1.0, 1.0])
    assert abs(scores_equal["doc_a"] - scores_equal["doc_b"]) < 1e-9

    # With weighted RRF, list2 gets priority
    scores_weighted = rrf_fuse([list1, list2], k=60, weights=[0.2, 1.0])
    assert scores_weighted["doc_b"] > scores_weighted["doc_a"]


def test_cross_encoder_heuristic_reranker_fallback():
    reranker = CrossEncoderReranker(model_name="nonexistent-mock-model")
    query = "database sqlite commit"
    docs = [
        "Name: unrelated\nDocstring: Web server router\nSource: def serve(): pass",
        "Name: RepoDatabase.commit\nDocstring: Commit to SQLite storage\nSource: def commit(): pass",
    ]
    ranked = reranker.rerank(query, docs, top_n=2)
    assert ranked[0] == 1  # Index 1 has strong symbol and lexical overlap


def test_sqlite_fts5_indexing_and_search(tmp_path):
    db_file = tmp_path / "test_fts.db"
    with RepoDatabase(db_file) as db:
        assert db.has_fts5 is True
        db.insert_fts_chunks([
            ("c1", "auth.py", "authenticate_user", "def authenticate_user(username, password): pass"),
            ("c2", "db.py", "connect", "def connect(db_path): return sqlite3.connect(db_path)"),
        ])
        db.commit()

        # Search for keyword
        results = db.search_fts("authenticate user")
        assert len(results) >= 1
        assert results[0][0] == "c1"

        # Delete by file
        db.delete_fts_by_file("auth.py")
        assert len(db.search_fts("authenticate")) == 0


def test_ast_cyclomatic_complexity_extraction():
    source = """
def complex_algorithm(x, y):
    if x > 0 and y > 0:
        for i in range(x):
            if i % 2 == 0:
                print(i)
    elif x < 0:
        try:
            return 10 / x
        except ZeroDivisionError:
            return 0
    return x + y
"""
    extractor = PythonExtractor(source)
    funcs = extractor.extract_functions(file_id=1)
    assert len(funcs) == 1
    # Base 1 + if(1) + and(1) + for(1) + if(1) + elif(1) + except(1) = 7
    assert funcs[0].complexity >= 6


def test_ast_symbol_call_extraction():
    source = """
def caller_function(data):
    clean = sanitize_input(data)
    db.insert_record(clean)
    return clean
"""
    extractor = PythonExtractor(source)
    calls = extractor.extract_calls(file_id=1, caller_file="service.py")
    callee_names = [c.callee_name for c in calls]
    assert "sanitize_input" in callee_names
    assert "db.insert_record" in callee_names
    assert all(c.caller_symbol == "caller_function" for c in calls)


def test_extract_file_backward_compatibility(tmp_path):
    py_file = tmp_path / "test_mod.py"
    py_file.write_text("def hello(): return 1\nclass Greeter: pass\nimport sys\n")
    # Test 3-variable unpack (old v1 caller)
    f, c, i = extract_file(py_file, file_id=1)
    assert len(f) == 1
    assert len(c) == 1
    assert len(i) == 1

    # Test 4-variable unpack (new v2 caller)
    f4, c4, i4, calls4 = extract_file(py_file, file_id=1)
    assert len(f4) == 1
    assert isinstance(calls4, list)


def test_blast_radius_and_transitive_dependents(tmp_path):
    db_file = tmp_path / "blast.db"
    with RepoDatabase(db_file) as db:
        id_a = db.insert_file("pkg/a.py", "h1", 10, 0.0)
        id_b = db.insert_file("pkg/b.py", "h2", 20, 0.0)
        id_c = db.insert_file("pkg/c.py", "h3", 30, 0.0)

        # c is imported by b, b is imported by a (a -> b -> c)
        db.insert_imports([
            from_import_rec(id_a, "pkg.b", "b"),
            from_import_rec(id_b, "pkg.c", "c"),
        ])
        db.insert_functions([
            FunctionRecord(id_c, "compute", "pkg.c.compute", 1, 10, None, "def compute(): pass", complexity=5),
        ])
        db.insert_symbol_calls([
            CallRecord(id_b, "pkg/b.py", "b_func", "compute", 4),
        ])
        db.commit()

    builder = GraphBuilder(db_file, tmp_path)
    builder.build()

    # If c changes, b and a are impacted
    res = builder.compute_blast_radius("pkg/c.py")
    assert "pkg/b.py" in res["direct_importers"]
    assert "pkg/a.py" in res["transitive_dependents"]
    assert res["blast_radius_count"] == 2
    assert res["complexity"]["max"] == 5


def from_import_rec(file_id: int, mod: str, name: str):
    from repomind.database import ImportRecord
    return ImportRecord(file_id, mod, name, True, 1)


def test_deterministic_citation_verification(tmp_path):
    db_file = tmp_path / "cite.db"
    with RepoDatabase(db_file) as db:
        db.insert_file("pkg/auth.py", "h1", 100, 0.0)
        db.commit()

    retrieved_metas = [
        {"file": "pkg/auth.py", "start": 10, "end": 40, "name": "login"},
    ]

    answer = "Authentication happens in [pkg/auth.py:15-30] and also [nonexistent.py:5]."
    verification = verify_citations(answer, retrieved_metas, db_file)

    assert verification["total_citations"] == 2
    assert verification["grounded_count"] == 1
    assert verification["verified_count"] == 1  # pkg/auth.py verified, nonexistent.py not found
    statuses = [c["status"] for c in verification["citations"]]
    assert "GROUNDED" in statuses
    assert "FILE_NOT_FOUND" in statuses


def test_composite_hotspot_and_bus_factor():
    git_stats = {
        "fragile.py": {
            "commit_count": 50,
            "lines_added": 200,
            "lines_deleted": 150,
            "author_count": 1,
            "top_author": "Alice",
            "top_author_pct": 100,
            "bus_factor_risk": True,
        },
        "stable.py": {
            "commit_count": 2,
            "lines_added": 10,
            "lines_deleted": 0,
            "author_count": 2,
            "top_author": "Bob",
            "top_author_pct": 50,
            "bus_factor_risk": False,
        },
    }
    complexities = {"fragile.py": 25, "stable.py": 2}
    pagerank = {"fragile.py": 0.15, "stable.py": 0.01}

    hotspots = GitAnalyzer.compute_composite_hotspots(git_stats, complexities, pagerank)
    assert len(hotspots) == 2
    assert hotspots[0]["path"] == "fragile.py"
    assert hotspots[0]["risk_level"] in ("HIGH", "CRITICAL")
    assert hotspots[0]["bus_factor_risk"] is True


def test_delta_vector_sync(tmp_path, monkeypatch):
    from repomind import rag as rag_mod

    db_path = tmp_path / "sync.db"
    with RepoDatabase(db_path) as db:
        fid = db.insert_file("pkg/test.py", "h1", 20, 0.0)
        db.insert_functions([
            FunctionRecord(fid, "func_1", "pkg.func_1", 1, 10, None, "def func_1(): pass"),
        ])
        db.commit()

    monkeypatch.setattr(
        "repomind.embedder.CodeEmbedder.embed_texts",
        lambda self, texts: [[0.1] * 8 for _ in texts],
    )

    import chromadb
    from chromadb.config import Settings

    rag = RepoRAG.__new__(RepoRAG)
    rag.db_path = db_path
    from repomind.config import load_config
    from repomind.embedder import CodeEmbedder

    rag.config = load_config()
    rag.embedder = CodeEmbedder()
    rag.chroma_client = chromadb.PersistentClient(
        path=str(tmp_path / "chroma"), settings=Settings(anonymized_telemetry=False)
    )
    rag.collection = rag.chroma_client.get_or_create_collection(
        name=rag_mod.COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
    )

    # Initial build
    rag.build_index()
    assert rag.collection.count() == 1

    # Delta sync: update file chunks
    new_chunks = [
        {
            "id": "func_1_new",
            "document": "def func_1_updated(): return True",
            "metadata": {"name": "func_1", "file": "pkg/test.py", "start": 1, "end": 15},
        }
    ]
    rag.sync_file_delta("pkg/test.py", new_chunks)
    assert rag.collection.count() == 1
    item = rag.collection.get(ids=["func_1_new"])
    assert len(item["ids"]) == 1


def test_mcp_server_protocol(tmp_path):
    db_file = tmp_path / "mcp.db"
    with RepoDatabase(db_file) as db:
        fid = db.insert_file("calc.py", "hash", 10, 0.0)
        db.insert_functions([
            FunctionRecord(fid, "add", "add", 1, 5, "Add two numbers", "def add(a, b): return a + b", complexity=2),
        ])
        db.commit()

    server = RepoMindMCPServer(db_path=db_file, repo_path=tmp_path)
    tools = server.get_tools_list()
    assert len(tools) == 4
    tool_names = [t["name"] for t in tools]
    assert "repomind_search" in tool_names
    assert "repomind_symbol_lookup" in tool_names
    assert "repomind_blast_radius" in tool_names
    assert "repomind_health_summary" in tool_names

    # Test symbol lookup tool
    out = server.handle_tool_call("repomind_symbol_lookup", {"symbol_name": "add"})
    assert "add" in out
    assert "Complexity: 2" in out

    # Test blast radius tool
    blast = server.handle_tool_call("repomind_blast_radius", {"target": "calc.py"})
    assert "calc.py" in blast

    # Test health summary tool
    health = server.handle_tool_call("repomind_health_summary", {})
    assert "health_score" in health
