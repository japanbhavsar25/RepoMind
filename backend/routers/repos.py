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
from backend.services.repo_manager import CloneFailedError, repo_manager

logger = logging.getLogger("repomind.repos")
router = APIRouter(prefix="/repos", tags=["Repositories"])

_github_adds: dict[str, deque[float]] = defaultdict(deque)
_github_adds_lock = threading.Lock()


_ALL_CLIENTS = "*"  # key for the server-wide count (never a real IP)


def _client_ip(request: Request) -> str:
    # Behind a proxy (e.g. Render) the real client is the LAST X-Forwarded-For hop:
    # the proxy appends it, while earlier entries are whatever the client sent
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def _recent_adds(key: str, now: float) -> deque[float]:
    """Clone times for this key within the last hour (call with the lock held)."""
    recent = _github_adds[key]
    while recent and now - recent[0] > 3600:
        recent.popleft()
    return recent


def _enforce_github_rate_limit(request: Request) -> None:
    """In public mode, cap clones per client IP and for the whole server, per hour."""
    if not settings.public_mode:
        return
    now = time.time()
    with _github_adds_lock:
        if len(_recent_adds(_client_ip(request), now)) >= settings.github_adds_per_hour:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Limit reached: {settings.github_adds_per_hour} repositories per hour. Try again later.",
            )
        if len(_recent_adds(_ALL_CLIENTS, now)) >= settings.github_adds_per_hour_total:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="The demo has cloned as many repositories as it can this hour. Try again later.",
            )


def _record_github_add(request: Request) -> None:
    """Charge one clone to the client and to the server-wide count."""
    if not settings.public_mode:
        return
    now = time.time()
    with _github_adds_lock:
        _recent_adds(_client_ip(request), now).append(now)
        _recent_adds(_ALL_CLIENTS, now).append(now)


def _reject_in_public_mode() -> None:
    if settings.public_mode:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Local folders are disabled on the public demo. Add a GitHub link instead.",
        )


def _reject_foreign_origin(request: Request) -> None:
    """Refuse browser requests from other websites (CSRF on a developer's local server)."""
    origin = request.headers.get("origin")
    if not origin:
        return  # not a cross-site browser request (curl, the CLI, same-origin GETs)
    allowed = origin in settings.cors_origins or any(
        origin.startswith(prefix) for prefix in ("http://localhost:", "http://127.0.0.1:")
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-origin request rejected.",
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
def add_local_repository(req: AddLocalRepoRequest, request: Request) -> RepoInfo:
    """Register a new local repository by folder path."""
    _reject_in_public_mode()
    _reject_foreign_origin(request)
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
    except (SecurityError, CloneFailedError) as e:
        # A bad link or a failed clone downloaded nothing, so it doesn't use up the quota
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except ValueError as e:
        _record_github_add(request)  # cloned, then rejected (no Python files, too many files)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except TimeoutError as e:
        _record_github_add(request)
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(e)) from e
    except Exception as e:
        _record_github_add(request)
        logger.error("GitHub repository ingestion failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add repository: {e}",
        ) from e

    if created:
        _record_github_add(request)
    else:
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
    _reject_foreign_origin(request)

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
def trigger_indexing(request: Request, repo_id: str | None = Query(None)) -> IndexRepoResponse:
    """Index or re-index the specified repository (defaults to active)."""
    # A body-less POST needs no CORS preflight, so check the Origin here
    _reject_foreign_origin(request)
    # On the public demo, only a newly added repo may be indexed (once). Re-indexing
    # wipes and rebuilds the index, which would break the demo for every visitor.
    if settings.public_mode and repo_manager.get_repo(repo_id).is_indexed():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Re-indexing is disabled on the public demo.",
        )
    try:
        res = repo_manager.index_repo(repo_id)
        return IndexRepoResponse(**res)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e
