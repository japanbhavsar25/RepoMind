"""Grounded question answering service with citation verification."""

from __future__ import annotations

from typing import Any

import requests

from backend.config import settings
from backend.services.repo_manager import repo_manager
from repomind.database import RepoDatabase
from repomind.hybrid import detect_query_intent
from repomind.llm import GroqClient, OllamaClient
from repomind.rag import RepoRAG, verify_citations


def get_llm_client() -> GroqClient | OllamaClient:
    """Pick the LLM backend: Groq when configured (or forced), else local Ollama."""
    provider = settings.llm_provider.lower()
    if provider == "groq" or (provider == "auto" and settings.groq_api_key):
        return GroqClient(api_key=settings.groq_api_key, model=settings.groq_model)
    return OllamaClient(
        model=settings.default_ollama_model,
        url=f"{settings.ollama_url.rstrip('/')}/api/generate",
    )


def llm_available(client: GroqClient | OllamaClient) -> bool:
    if isinstance(client, GroqClient):
        return client.is_alive()
    try:
        return requests.get(f"{settings.ollama_url}/api/tags", timeout=1.5).status_code == 200
    except Exception:
        return False


class LLMUnavailableError(RuntimeError):
    """The language model was reachable but failed to produce an answer."""


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
                "citation_confidence": None,
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
                            "kind": _kind_val,
                            "start": lstart or 1,
                            "end": lend or (lstart or 1),
                        })
                        if len(docs) >= top_k:
                            break

        if not docs:
            return {
                "question": question,
                "answer": "No relevant code chunks could be retrieved for this query.",
                "citations": [],
                "citation_confidence": None,
                "intent": intent_label,
                "model_used": "none",
                "chunks_retrieved": 0,
            }

        # Build citations from retrieved evidence. "verified" is set below, only for
        # snippets a grounded citation in the written answer points into.
        citations: list[dict[str, Any]] = []
        for doc, meta in zip(docs, metas, strict=False):
            citations.append({
                "file_path": meta.get("file", ""),
                "line_start": meta.get("start", 1),
                "line_end": meta.get("end", meta.get("start", 1)),
                "snippet": doc[:300] + ("..." if len(doc) > 300 else ""),
                "verified": False,
            })

        llm = get_llm_client()
        llm_active = use_llm and llm_available(llm)

        if not llm_active:
            summary_lines = [
                f"### Relevant Evidence Retrieved ({len(docs)} code chunks)",
                "AI answers are off: set GROQ_API_KEY in .env, or run a local Ollama server at "
                f"`{settings.ollama_url}`.",
                "",
                "**Top Matching Sources:**",
            ]
            for c in citations[:5]:
                summary_lines.append(f"- `[{c['file_path']}:{c['line_start']}-{c['line_end']}]`")

            return {
                "question": question,
                "answer": "\n".join(summary_lines),
                "citations": citations,
                "citation_confidence": None,  # no written answer, so nothing to verify
                "intent": intent_label,
                "model_used": "none (evidence only)",
                "chunks_retrieved": len(docs),
            }

        # LLM available -> grounded answer from the chunks we already retrieved.
        # An LLM failure raises LLMUnavailableError: the router turns it into a 502,
        # rather than a 200 whose "answer" is an error message with a score attached.
        prompt, system = rag.build_prompt(question, docs, metas)
        try:
            raw_answer = llm.generate(prompt, system=system, temperature=0.2)
        except Exception as exc:
            raise LLMUnavailableError(f"The language model couldn't answer: {exc}") from exc
        # Some models (e.g. gpt-oss) cite with CJK lenticular brackets; normalize for the verifier
        raw_answer = raw_answer.replace("【", "[").replace("】", "]")
        v_report = verify_citations(raw_answer, metas, repo.db_path)
        grounded = [c for c in v_report["citations"] if c["status"] == "GROUNDED"]
        for c in citations:
            c["verified"] = any(
                g["file"] == c["file_path"] and c["line_start"] <= g["lines"][0] and g["lines"][1] <= c["line_end"]
                for g in grounded
            )
        usage = getattr(llm, "last_usage", {}) or {}
        return {
            "question": question,
            "answer": raw_answer,
            "citations": citations,
            "citation_confidence": v_report["confidence_score"],
            "intent": intent_label,
            "model_used": llm.model,
            "chunks_retrieved": len(docs),
            "latency_ms": usage.get("latency_ms"),
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
        }


qa_service = QAService()
