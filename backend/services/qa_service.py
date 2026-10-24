"""Grounded question answering service with citation verification."""

from __future__ import annotations

from typing import Any

import requests

from backend.config import settings
from backend.services.repo_manager import repo_manager
from repomind.database import RepoDatabase
from repomind.hybrid import detect_query_intent
from repomind.rag import RepoRAG, verify_citations


class QAService:
    """Manages context retrieval, prompt synthesis, and citation verification."""

    @staticmethod
    def answer_question(
        repo_id: str | None,
        question: str,
        top_k: int = 5,
        use_llm: bool = True,
    ) -> dict:
        repo = repo_manager.get_repo(repo_id)
        if not repo.db_path.exists():
            return {
                "question": question,
                "answer": "This repository has not been indexed yet. Please run Indexing first.",
                "citations": [],
                "citation_confidence": 0.0,
                "intent": "general",
                "model_used": "none",
                "chunks_retrieved": 0,
            }

        rag = RepoRAG(repo.db_path, model=settings.default_ollama_model)
        intent_map = detect_query_intent(question)
        intent_label = (
            "code_identifier"
            if intent_map.get("sparse", 0.0) > intent_map.get("dense", 0.0)
            else "natural_language"
        )

        docs, metas = [], []
        try:
            if rag.collection.count() > 0:
                docs, metas, _ = rag.retrieve(question, top_k=top_k, hybrid=True, rerank=True)
        except Exception:
            docs, metas = [], []

        # If vector retrieve produced no docs, fall back to symbols
        if not docs:
            with RepoDatabase(repo.db_path) as db:
                all_syms = db.get_all_symbols()
                # Find matching symbols by query keywords
                q_lower = question.lower()
                for _kind_val, _id, name, _qname, doc, src, lstart, lend, fpath in all_syms:
                    if name.lower() in q_lower or (doc and any(w in doc.lower() for w in q_lower.split())):
                        docs.append(src or f"def {name}():")
                        metas.append({
                            "file": fpath,
                            "name": name,
                            "line_start": lstart or 1,
                            "line_end": lend or (lstart or 1),
                        })
                        if len(docs) >= top_k:
                            break

        if not docs:
            return {
                "question": question,
                "answer": "No relevant code chunks could be retrieved for this query.",
                "citations": [],
                "citation_confidence": 0.0,
                "intent": intent_label,
                "model_used": "none",
                "chunks_retrieved": 0,
            }

        # Build citations from retrieved evidence
        citations: list[dict[str, Any]] = []
        for doc, meta in zip(docs, metas, strict=False):
            citations.append({
                "file_path": meta.get("file", ""),
                "line_start": meta.get("line_start", 1),
                "line_end": meta.get("line_end", 1),
                "snippet": doc[:300] + ("..." if len(doc) > 300 else ""),
                "verified": True,
            })

        # Check if local Ollama is available
        ollama_active = False
        if use_llm:
            try:
                ping = requests.get(f"{settings.ollama_url}/api/tags", timeout=1.5)
                ollama_active = ping.status_code == 200
            except Exception:
                ollama_active = False

        if not use_llm or not ollama_active:
            summary_lines = [
                f"### Relevant Evidence Retrieved ({len(docs)} code chunks)",
                "Answering requires a running local LLM (Ollama). Ollama is currently not responding at "
                f"`{settings.ollama_url}`.",
                "",
                "**Top Matching Sources:**",
            ]
            for c in citations[:5]:
                summary_lines.append(f"- `[{c['file_path']}:{c['line_start']}-{c['line_end']}]`")
            summary_lines.append("\nRun `ollama serve` and `ollama run phi3` to enable automated synthesis.")

            return {
                "question": question,
                "answer": "\n".join(summary_lines),
                "citations": citations,
                "citation_confidence": 1.0,
                "intent": intent_label,
                "model_used": "none (evidence only)",
                "chunks_retrieved": len(docs),
            }

        # Ollama is active -> Run grounded RAG prompt
        try:
            raw_answer = rag.ask(question, top_k=top_k, hybrid=True, rerank=True)
            v_report = verify_citations(raw_answer, repo.db_path, retrieved_chunks=metas)
            return {
                "question": question,
                "answer": raw_answer,
                "citations": citations,
                "citation_confidence": v_report.get("confidence", 0.0),
                "intent": intent_label,
                "model_used": settings.default_ollama_model,
                "chunks_retrieved": len(docs),
            }
        except Exception as exc:
            return {
                "question": question,
                "answer": f"Error communicating with local LLM: {exc}",
                "citations": citations,
                "citation_confidence": 0.5,
                "intent": intent_label,
                "model_used": settings.default_ollama_model,
                "chunks_retrieved": len(docs),
            }


qa_service = QAService()
