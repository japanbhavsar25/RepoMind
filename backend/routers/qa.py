"""Grounded Q&A router."""


from fastapi import APIRouter, HTTPException, Query, status

from backend.schemas import AskRequest, AskResponse
from backend.services.qa_service import LLMUnavailableError, qa_service

router = APIRouter(prefix="/ask", tags=["Grounded Q&A"])


@router.post("", response_model=AskResponse)
def ask_codebase(req: AskRequest, repo_id: str | None = Query(None)) -> AskResponse:
    """Answer questions about the codebase grounded in retrieved source evidence."""
    try:
        res = qa_service.answer_question(
            repo_id=repo_id,
            question=req.question,
            top_k=req.top_k,
            use_llm=req.use_llm,
        )
        return AskResponse(**res)
    except LLMUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
