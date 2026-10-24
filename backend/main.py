"""FastAPI application entrypoint for RepoMind."""

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
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
    try:
        from repomind.embedder import CodeEmbedder
        from repomind.hybrid import CrossEncoderReranker

        CodeEmbedder().embed_texts(["warm up"])
        CrossEncoderReranker()._load()
        logger.info("Search models loaded and ready.")
    except Exception as exc:
        logger.warning("Model warm-up failed (first query will load them): %s", exc)


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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers under /api
app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(repos.router, prefix=settings.api_prefix)
app.include_router(files.router, prefix=settings.api_prefix)
app.include_router(symbols.router, prefix=settings.api_prefix)
app.include_router(search.router, prefix=settings.api_prefix)
app.include_router(qa.router, prefix=settings.api_prefix)
app.include_router(graph.router, prefix=settings.api_prefix)
app.include_router(impact.router, prefix=settings.api_prefix)
app.include_router(evaluate.router, prefix=settings.api_prefix)


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
