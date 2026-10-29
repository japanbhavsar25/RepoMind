"""Graph visualization and cycle analysis router."""


from fastapi import APIRouter, Query

from backend.errors import internal_error
from backend.schemas import GraphDataResponse
from backend.services.graph_service import graph_service

router = APIRouter(prefix="/graph", tags=["Architecture Graph"])


@router.get("", response_model=GraphDataResponse)
def get_dependency_graph(repo_id: str | None = Query(None)) -> GraphDataResponse:
    """Fetch complete graph nodes, edges, cycles, and PageRank rankings."""
    try:
        res = graph_service.get_graph_data(repo_id)
        return GraphDataResponse(**res)
    except Exception as exc:
        raise internal_error("Building the dependency graph", exc) from exc


@router.get("/cycles")
def get_cycles(repo_id: str | None = Query(None)):
    """Return circular dependency cycles."""
    try:
        res = graph_service.get_graph_data(repo_id)
        return {"cycles": res["cycles"], "count": len(res["cycles"])}
    except Exception as exc:
        raise internal_error("Building the dependency graph", exc) from exc


@router.get("/orphans")
def get_orphans(repo_id: str | None = Query(None)):
    """Return orphan files with zero internal connections."""
    try:
        res = graph_service.get_graph_data(repo_id)
        return {"orphans": res["orphans"], "count": len(res["orphans"])}
    except Exception as exc:
        raise internal_error("Building the dependency graph", exc) from exc
