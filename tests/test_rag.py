# tests/test_rag.py
"""Tests for chunked index, incremental embed, hybrid retrieve, citations."""

import pytest

from repomind.database import ClassRecord, FunctionRecord, RepoDatabase
from repomind.llm import OllamaError
from repomind.rag import RepoRAG


@pytest.fixture()
def db_path(tmp_path):
    p = tmp_path / "t.db"
    with RepoDatabase(p) as db:
        fid = db.insert_file("pkg/a.py", "h1", 50, 0.0)
        db.insert_functions([
            FunctionRecord(fid, "alpha", "pkg.alpha", 1, 10, "Alpha does X.", "def alpha():\n    return 1\n"),
        ])
        db.insert_classes([
            ClassRecord(fid, "Beta", "pkg.Beta", 20, 30, None, "class Beta:\n    pass\n"),
        ])
        db.commit()
    return p


@pytest.fixture()
def mocked_rag(db_path, tmp_path, monkeypatch):
    # Avoid real model download + real Chroma location + real Ollama
    from repomind import rag as rag_mod

    monkeypatch.setattr(
        "repomind.embedder.CodeEmbedder.embed_texts",
        lambda self, texts: [[float(len(t) % 7)] * 8 for t in texts],
    )
    r = RepoRAG.__new__(RepoRAG)
    # minimal manual init with tmp chroma
    import chromadb
    from chromadb.config import Settings

    from repomind.config import load_config
    from repomind.embedder import CodeEmbedder
    from repomind.llm import OllamaClient

    r.db_path = db_path
    r.config = load_config()
    r.embedder = CodeEmbedder()
    r.llm = OllamaClient(model="phi3")
    r.chroma_client = chromadb.PersistentClient(
        path=str(tmp_path / "chroma"), settings=Settings(anonymized_telemetry=False)
    )
    r.collection = r.chroma_client.get_or_create_collection(
        name=rag_mod.COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
    )
    return r


def test_build_index_chunks_and_incremental_skip(mocked_rag):
    s1 = mocked_rag.build_index()
    assert s1["total"] == 2
    assert s1["added_or_updated"] == 2
    s2 = mocked_rag.build_index()
    assert s2["skipped"] == 2
    assert s2["added_or_updated"] == 0
    # metadata has lines for citations
    data = mocked_rag.collection.get(include=["metadatas"])
    assert all("start" in m and "end" in m for m in data["metadatas"])


def test_retrieve_vector_and_hybrid(mocked_rag):
    mocked_rag.build_index()
    docs, metas, ids = mocked_rag.retrieve("alpha", top_k=2, hybrid=False)
    assert len(docs) >= 1
    docs_h, metas_h, _ = mocked_rag.retrieve("alpha", top_k=2, hybrid=True)
    assert len(docs_h) >= 1
    assert any("pkg/a.py" in m.get("file", "") for m in metas_h)


def test_ask_requires_citations_prompt_and_alive(mocked_rag, monkeypatch):
    mocked_rag.build_index()
    monkeypatch.setattr("repomind.llm.OllamaClient.is_alive", lambda self: True)
    seen = {}

    def fake_gen(self, prompt, system=None, temperature=0.2):
        seen["prompt"] = prompt
        seen["system"] = system
        return "answer [pkg/a.py:1-10]"

    monkeypatch.setattr("repomind.llm.OllamaClient.generate", fake_gen)
    ans = mocked_rag.ask("what does alpha do?")
    assert "pkg/a.py" in ans
    assert "Cite" in seen["prompt"] or "cite" in seen["prompt"].lower()
    assert "CODE CONTEXT" in seen["prompt"]

    monkeypatch.setattr("repomind.llm.OllamaClient.is_alive", lambda self: False)
    with pytest.raises(OllamaError):
        mocked_rag.ask("q?")
