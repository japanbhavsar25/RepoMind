"""Retrieval evaluation router."""


from fastapi import APIRouter, HTTPException, Query, status

from backend.schemas import EvaluationResponse
from backend.services.eval_service import eval_service

router = APIRouter(prefix="/evaluate", tags=["Evaluation"])


@router.get("", response_model=EvaluationResponse)
def get_evaluation(repo_id: str | None = Query(None), max_samples: int = Query(10)) -> EvaluationResponse:
    """Run quantitative retrieval benchmark comparing Dense vs. Sparse vs. Hybrid RRF."""
    try:
        res = eval_service.run_eval(repo_id=repo_id, max_samples=max_samples)
        return EvaluationResponse(**res)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
