"""Symbols complexity per definition, and benchmark questions scoped to the repo."""

from types import SimpleNamespace

from backend.routers import symbols as symbols_router
from backend.services import eval_service as eval_mod
from repomind.database import FunctionRecord, RepoDatabase


def _db_with_two_inits(path):
    with RepoDatabase(path) as db:
        fid = db.insert_file("pkg/a.py", "h1", 50, 0.0)
        db.insert_functions([
            FunctionRecord(fid, "__init__", "Small.__init__", 1, 3, None, "def __init__(self): pass", complexity=1),
            FunctionRecord(fid, "__init__", "Big.__init__", 10, 30, None, "def __init__(self): ...", complexity=9),
        ])
        db.commit()


def test_same_named_functions_keep_their_own_complexity(tmp_path, monkeypatch):
    db_file = tmp_path / "s.db"
    _db_with_two_inits(db_file)
    monkeypatch.setattr(symbols_router.repo_manager, "get_repo", lambda _id: SimpleNamespace(db_path=db_file))

    listed = symbols_router.list_symbols(kind=None, repo_id="any")
    by_qname = {s.qualified_name: s.complexity for s in listed.symbols}
    assert by_qname == {"Small.__init__": 1, "Big.__init__": 9}

    assert symbols_router.get_symbol_detail("Big.__init__", repo_id="any")["complexity"] == 9


def test_gold_questions_only_for_repomind_itself(tmp_path, monkeypatch):
    db_file = tmp_path / "e.db"
    db_file.touch()
    seen = {}

    class _FakeEvaluator:
        def __init__(self, db_path):
            pass

        def run_full_evaluation(self, gold_path=None, max_samples=15):
            seen["gold"] = gold_path
            return {}

    monkeypatch.setattr(eval_mod, "RetrievalEvaluator", _FakeEvaluator)
    for repo_id, uses_gold in [("ecommerce_sample", False), ("repomind_core", True)]:
        repo = SimpleNamespace(id=repo_id, db_path=db_file)
        monkeypatch.setattr(eval_mod.repo_manager, "get_repo", lambda _id, r=repo: r)
        eval_mod.EvalService.run_eval(repo_id)
        assert (seen["gold"] is not None) is uses_gold, repo_id
