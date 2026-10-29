"""Health and system diagnostics router."""

from fastapi import APIRouter

from backend.config import settings
from backend.schemas import HealthResponse
from repomind.database import RepoDatabase

router = APIRouter(prefix="/health", tags=["Diagnostics"])


@router.get("", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Return system status, version, and database FTS5 capabilities."""
    fts5_ok = False
    try:
        # Check SQLite FTS5 support on a memory test connection
        with RepoDatabase(settings.data_dir / "health_check.db") as db:
            fts5_ok = db._has_fts5
    except Exception:
        fts5_ok = False

    return HealthResponse(
        status="healthy",
        version=settings.version,
        fts5_enabled=fts5_ok,
        data_dir="" if settings.public_mode else str(settings.data_dir),  # no server paths on the demo
        local_repos_enabled=not settings.public_mode,
    )
