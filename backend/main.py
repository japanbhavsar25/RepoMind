"""FastAPI application entrypoint for RepoMind."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: ensure sample repository is indexed at startup."""
    logger.info("Initializing RepoMind backend (v%s)...", settings.version)
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


@app.get("/")
def root():
    """Root info endpoint."""
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
