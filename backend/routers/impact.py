"""Change-impact and downstream blast radius router."""


from fastapi import APIRouter, Query

from backend.errors import internal_error
from backend.schemas import ImpactResponse
from backend.services.graph_service import graph_service

router = APIRouter(prefix="/impact", tags=["Change Impact"])


@router.get("/{target:path}", response_model=ImpactResponse)
def analyze_impact(target: str, repo_id: str | None = Query(None)) -> ImpactResponse:
    """Analyze downstream blast radius, direct callers, and transitive dependents of a module or symbol."""
    try:
        res = graph_service.compute_impact(target=target, repo_id=repo_id)
        return ImpactResponse(**res)
    except Exception as exc:
        raise internal_error("Impact analysis", exc) from exc
