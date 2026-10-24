"""Hybrid search service combining FTS5 lexical matching and dense vectors."""

from __future__ import annotations

from typing import Any

from backend.services.repo_manager import repo_manager
from repomind.database import RepoDatabase
from repomind.hybrid import detect_query_intent
from repomind.rag import RepoRAG


class SearchService:
    """Coordinates hybrid, sparse, and symbol code search."""

    @staticmethod
    def execute_search(
        repo_id: str | None,
        query: str,
        top_k: int = 5,
        filter_type: str | None = None,
        filter_path: str | None = None,
    ) -> dict:
        repo = repo_manager.get_repo(repo_id)
        if not repo.db_path.exists():
            return {
                "query": query,
                "intent": "general",
                "results": [],
                "total_candidates": 0,
            }

        intent_map = detect_query_intent(query)
        intent_label = (
            "code_identifier"
            if intent_map.get("sparse", 0.0) > intent_map.get("dense", 0.0)
            else "natural_language"
        )

        rag = RepoRAG(repo.db_path)
        docs, metas, ids = [], [], []

        # Try RAG retrieval if collection has chunks
        try:
            if rag.collection.count() > 0:
                docs, metas, ids = rag.retrieve(
                    query, top_k=max(top_k * 2, 20), hybrid=True, rerank=True
                )
        except Exception:
            docs, metas, ids = [], [], []

        results: list[dict[str, Any]] = []

        # If vector retrieve produced results
        if docs:
            for rank, (doc, meta, chunk_id) in enumerate(zip(docs, metas, ids, strict=False), 1):
                c_type = meta.get("kind", "code")
                f_path = meta.get("file", "")

                if filter_type and c_type.lower() != filter_type.lower():
                    continue
                if filter_path and filter_path.lower() not in f_path.lower():
                    continue

                score = round(1.0 / (1.0 + (rank - 1) * 0.15), 4)
                results.append({
                    "chunk_id": str(chunk_id),
                    "file_path": f_path,
                    "snippet": doc[:400] + ("..." if len(doc) > 400 else ""),
                    "line_start": meta.get("line_start", 1),
                    "line_end": meta.get("line_end", 1),
                    "score": score,
                    "match_type": "hybrid",
                })
        else:
            # Fallback 1: SQLite FTS5 sparse search
            with RepoDatabase(repo.db_path) as db:
                if db.has_fts5:
                    try:
                        fts_hits = db.search_fts(query, limit=top_k * 2)
                        for cid, score in fts_hits:
                            results.append({
                                "chunk_id": cid,
                                "file_path": cid.split(":")[0] if ":" in cid else "",
                                "snippet": f"Matched FTS chunk {cid}",
                                "line_start": 1,
                                "line_end": 1,
                                "score": round(score, 4),
                                "match_type": "fts5_sparse",
                            })
                    except Exception:
                        pass

                # Fallback 2: Symbol matching in database
                if not results:
                    sym_hits = db.search(query, limit=top_k * 2)
                    # sym_hits: (type, name, qualified_name, line_start, line_end, file_path)
                    all_syms = db.get_all_symbols()
                    src_map = {s[2]: s[5] for s in all_syms}  # name -> source_code

                    for hit in sym_hits[:top_k]:
                        stype, sname, sqname, slstart, slend, sfpath = hit
                        src = src_map.get(sname, "")
                        results.append({
                            "chunk_id": f"sym_{sname}",
                            "file_path": sfpath,
                            "snippet": (src[:400] + "...") if len(src) > 400 else (src or f"def {sname}():"),
                            "line_start": slstart or 1,
                            "line_end": slend or (slstart or 1),
                            "score": 0.85,
                            "match_type": "symbol_exact",
                        })

        return {
            "query": query,
            "intent": intent_label,
            "results": results[:top_k],
            "total_candidates": len(results),
        }


search_service = SearchService()
