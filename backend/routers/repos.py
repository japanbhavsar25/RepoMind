"""Repository management and indexing triggers router."""

import logging

from fastapi import APIRouter, HTTPException, Query, Request, status

from backend.config import settings
from backend.schemas import (
    AddLocalRepoRequest,
    BrowseFolderRequest,
    BrowseFolderResponse,
    IndexRepoResponse,
    RepoInfo,
    RepoListResponse,
    RepoStats,
    SelectRepoRequest,
)
from backend.services.folder_picker import pick_folder_native
from backend.services.repo_manager import repo_manager

logger = logging.getLogger("repomind.repos")
router = APIRouter(prefix="/repos", tags=["Repositories"])


@router.get("", response_model=RepoListResponse)
def list_repositories() -> RepoListResponse:
    """Return all available repositories and the currently active repo ID."""
    repos = []
    for r in repo_manager.list_repos():
        s = r.get_stats()
        repos.append(
            RepoInfo(
                id=r.id,
                name=r.name,
                path=str(r.root_path),
                is_sample=r.is_sample,
                is_indexed=r.is_indexed(),
                stats=RepoStats(**s),
            )
        )
    return RepoListResponse(repos=repos, active_repo_id=repo_manager.active_repo_id)


@router.post("/select")
def select_repository(req: SelectRepoRequest):
    """Switch the active repository context."""
    try:
        repo = repo_manager.set_active_repo(req.repo_id)
        return {"status": "success", "active_repo_id": repo.id, "name": repo.name}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post("/local", response_model=RepoInfo, status_code=status.HTTP_201_CREATED)
def add_local_repository(req: AddLocalRepoRequest) -> RepoInfo:
    """Register a new local repository by folder path."""
    try:
        repo = repo_manager.add_local_repo(req.name, req.path)
        s = repo.get_stats()
        return RepoInfo(
            id=repo.id,
            name=repo.name,
            path=str(repo.root_path),
            is_sample=False,
            is_indexed=repo.is_indexed(),
            stats=RepoStats(**s),
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except ValueError as e:
        msg = str(e)
        if "already registered" in msg.lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg) from e
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register repository: {e}",
        ) from e


@router.post("/browse", response_model=BrowseFolderResponse)
async def browse_folder(
    request: Request,
    req: BrowseFolderRequest = BrowseFolderRequest(),
) -> BrowseFolderResponse:
    """Open a native Windows folder-selection dialog and return the chosen path.

    Non-blocking: executes in an isolated subprocess (see backend.services.folder_picker)
    so Tkinter never runs inside FastAPI's event loop or a worker thread.
    Restricted to local clients (127.0.0.1 / localhost) to prevent cross-origin abuse.
    """
    # 1. Enforce local-only client connection
    client_host = request.client.host if request.client else ""
    if client_host not in ("127.0.0.1", "::1", "localhost", "testclient"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: folder picker is restricted to local machine clients.",
        )

    # 2. Check Origin header if present (CORS/CSRF protection)
    origin = request.headers.get("origin")
    if origin:
        allowed = set(settings.cors_origins)
        is_allowed = origin in allowed or any(
            origin.startswith(prefix) for prefix in ("http://localhost:", "http://127.0.0.1:")
        )
        if not is_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cross-origin browse request rejected.",
            )

    # 3. Validate initial_path parameter if provided
    if req.initial_path and "\0" in req.initial_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid initial path: null bytes are forbidden.",
        )

    # 4. Open native dialog via isolated subprocess without blocking the event loop
    try:
        status_str, selected_path, error_msg = await pick_folder_native(
            initial_dir=req.initial_path,
            timeout_seconds=120.0,
        )
        if status_str == "selected":
            return BrowseFolderResponse(status="selected", path=selected_path, cancelled=False)
        elif status_str == "cancelled":
            return BrowseFolderResponse(status="cancelled", path=None, cancelled=True, error=error_msg)
        else:
            return BrowseFolderResponse(status="error", path=None, cancelled=False, error=error_msg)
    except Exception as exc:
        logger.error("Native folder picker error: %s", exc)
        return BrowseFolderResponse(status="error", path=None, cancelled=False, error=str(exc))


@router.post("/index", response_model=IndexRepoResponse)
def trigger_indexing(repo_id: str | None = Query(None)) -> IndexRepoResponse:
    """Index or re-index the specified repository (defaults to active)."""
    try:
        res = repo_manager.index_repo(repo_id)
        return IndexRepoResponse(**res)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e
