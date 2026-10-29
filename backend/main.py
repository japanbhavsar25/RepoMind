"""FastAPI application entrypoint for RepoMind."""

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.routers import (
    evaluate,
    files,
    graph,
    health,
    impact,
    qa,
    repos,
    search,
    symbols,
)
from backend.services.repo_manager import repo_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("repomind.api")


def _warm_up_models() -> None:
    """Load the embedding and reranker models once so the first question is fast."""
    from repomind.embedder import CodeEmbedder, embed_backend
    from repomind.hybrid import CrossEncoderReranker

    try:
        CodeEmbedder().embed_texts(["warm up"])
        logger.info("Embedding model ready (%s backend).", embed_backend())
    except Exception as exc:
        logger.warning("Embedding warm-up failed (first query will load it): %s", exc)
    try:
        CrossEncoderReranker()._load()
        logger.info("Cross-encoder reranker ready.")
    except Exception:
        logger.info("Cross-encoder not installed; using heuristic reranking (slim mode).")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: ensure sample repository is indexed at startup."""
    logger.info("Initializing RepoMind backend (v%s)...", settings.version)
    if settings.warmup_models:
        # Background thread: the server starts accepting requests immediately
        threading.Thread(target=_warm_up_models, daemon=True).start()
    try:
        sample_repo = repo_manager.get_repo("ecommerce_sample")
        if not sample_repo.is_indexed():
            logger.info("Indexing bundled sample repository (ecommerce_sample)...")
            repo_manager.index_repo("ecommerce_sample")
    except Exception as exc:
        logger.warning("Could not auto-index sample repo at startup: %s", exc)
    yield
    logger.info("RepoMind backend shutting down.")


app = FastAPI(
    title=settings.project_name,
    version=settings.version,
    description="Local-first code intelligence web API and RAG engine.",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,  # the web app sends no cookies or auth headers
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_known_repo(repo_id: str | None = Query(None)) -> None:
    """404 for a repo_id the server doesn't know, instead of quietly using the default repo."""
    if repo_id and not repo_manager.has_repo(repo_id):
        raise HTTPException(status_code=404, detail=f"Unknown repository: '{repo_id}'")


# Register routers under /api. Every router that reads ?repo_id= checks it first.
app.include_router(health.router, prefix=settings.api_prefix)
for module in (repos, files, symbols, search, qa, graph, impact, evaluate):
    app.include_router(module.router, prefix=settings.api_prefix, dependencies=[Depends(require_known_repo)])


FRONTEND_DIST = settings.base_dir / "frontend" / "dist"

if FRONTEND_DIST.is_dir():
    # Production: serve the built React app from the same server (single container)
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
else:

    @app.get("/")
    def root():
        """Root info endpoint (dev mode: the frontend runs on Vite instead)."""
        return {
            "name": settings.project_name,
            "version": settings.version,
            "docs_url": "/docs",
            "health_url": f"{settings.api_prefix}/health",
        }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions and format a clean JSON error response."""
    logger.error("Unhandled error on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred", "error": str(exc)},
    )
