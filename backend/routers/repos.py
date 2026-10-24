"""Repository management and indexing triggers router."""

import logging
import threading
import time
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Query, Request, Response, status

from backend.config import settings
from backend.schemas import (
    AddGitHubRepoRequest,
    AddLocalRepoRequest,
    BrowseFolderRequest,
    BrowseFolderResponse,
    IndexRepoResponse,
    RepoInfo,
    RepoListResponse,
    RepoStats,
    SelectRepoRequest,
)
from backend.security import SecurityError
from backend.services.folder_picker import pick_folder_native
from backend.services.repo_manager import repo_manager

logger = logging.getLogger("repomind.repos")
router = APIRouter(prefix="/repos", tags=["Repositories"])

_github_adds: dict[str, deque[float]] = defaultdict(deque)
_github_adds_lock = threading.Lock()


def _client_ip(request: Request) -> str:
    # Behind a proxy (e.g. Hugging Face Spaces) the real client is the first X-Forwarded-For hop
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _enforce_github_rate_limit(request: Request) -> None:
    """In public mode, allow each client IP a limited number of clones per hour."""
    if not settings.public_mode:
        return
    ip = _client_ip(request)
    now = time.time()
    with _github_adds_lock:
        recent = _github_adds[ip]
        while recent and now - recent[0] > 3600:
            recent.popleft()
        if len(recent) >= settings.github_adds_per_hour:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Limit reached: {settings.github_adds_per_hour} repositories per hour. Try again later.",
            )
        recent.append(now)


def _reject_in_public_mode() -> None:
    if settings.public_mode:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Local folders are disabled on the public demo. Add a GitHub link instead.",
        )


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
    _reject_in_public_mode()
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


@router.post("/github", response_model=RepoInfo, status_code=status.HTTP_201_CREATED)
def add_github_repository(req: AddGitHubRepoRequest, request: Request, response: Response) -> RepoInfo:
    """Clone a public GitHub repository and register it (201 if new, 200 if already added)."""
    _enforce_github_rate_limit(request)
    try:
        repo, created = repo_manager.add_github_repo(req.url)
    except (SecurityError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except TimeoutError as e:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(e)) from e
    except Exception as e:
        logger.error("GitHub repository ingestion failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add repository: {e}",
        ) from e

    if not created:
        response.status_code = status.HTTP_200_OK
    return RepoInfo(
        id=repo.id,
        name=repo.name,
        path=str(repo.root_path),
        is_sample=False,
        is_indexed=repo.is_indexed(),
        stats=RepoStats(**repo.get_stats()),
    )


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
    _reject_in_public_mode()
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
