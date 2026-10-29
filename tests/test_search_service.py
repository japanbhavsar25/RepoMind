"""Search service: hybrid results carry the chunk's real line range."""

from types import SimpleNamespace

from backend.services import search_service
from backend.services.search_service import SearchService


class _FakeRAG:
    """Stands in for RepoRAG: one indexed chunk, metadata shaped like build_index writes it."""

    def __init__(self, db_path):
        self.collection = SimpleNamespace(count=lambda: 1)

    def retrieve(self, query, top_k=5, hybrid=False, rerank=False):
        meta = {"file": "pkg/a.py", "kind": "function", "start": 12, "end": 40}
        return ["def alpha(): ..."], [meta], ["pkg/a.py:alpha"]


def test_hybrid_results_use_chunk_line_range(tmp_path, monkeypatch):
    db_file = tmp_path / "t.db"
    db_file.touch()
    monkeypatch.setattr(search_service.repo_manager, "get_repo", lambda _id: SimpleNamespace(db_path=db_file))
    monkeypatch.setattr(search_service, "RepoRAG", _FakeRAG)

    res = SearchService.execute_search("any", "where is alpha defined")

    hit = res["results"][0]
    assert hit["match_type"] == "hybrid"
    assert (hit["line_start"], hit["line_end"]) == (12, 40)
