"""Search API endpoint."""


from fastapi import APIRouter, HTTPException, Query, status

from backend.schemas import SearchRequest, SearchResponse
from backend.services.search_service import search_service

router = APIRouter(prefix="/search", tags=["Search"])


@router.post("", response_model=SearchResponse)
def search_code(req: SearchRequest, repo_id: str | None = Query(None)) -> SearchResponse:
    """Execute code search using hybrid RRF, FTS5 sparse search, or exact symbol lookup."""
    try:
        res = search_service.execute_search(
            repo_id=repo_id,
            query=req.query,
            top_k=req.top_k,
            filter_type=req.filter_type,
            filter_path=req.filter_path,
        )
        return SearchResponse(**res)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
