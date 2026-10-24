"""Pydantic schemas and contract definitions for RepoMind API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class HealthResponse(BaseModel):
    status: str
    version: str
    fts5_enabled: bool
    data_dir: str
    local_repos_enabled: bool = True


class RepoStats(BaseModel):
    files: int = 0
    functions: int = 0
    classes: int = 0
    imports: int = 0


class RepoInfo(BaseModel):
    id: str
    name: str
    path: str
    is_sample: bool = False
    is_indexed: bool = False
    stats: RepoStats | None = None


class RepoListResponse(BaseModel):
    repos: list[RepoInfo]
    active_repo_id: str


class SelectRepoRequest(BaseModel):
    repo_id: str


class AddLocalRepoRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Display name for the repository")
    path: str = Field(..., min_length=1, description="Absolute or relative local folder path")

    @field_validator("name", "path")
    @classmethod
    def strip_and_check_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Field cannot be empty or purely whitespace")
        return s


class AddGitHubRepoRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=300, description="Public HTTPS repository URL")


class BrowseFolderRequest(BaseModel):
    initial_path: str | None = None


class BrowseFolderResponse(BaseModel):
    status: str
    path: str | None = None
    cancelled: bool = False
    error: str | None = None


class ImportGitRepoRequest(BaseModel):
    url: str
    name: str | None = None


class IndexRepoResponse(BaseModel):
    status: str
    repo_id: str
    files_indexed: int
    functions_indexed: int
    classes_indexed: int
    imports_indexed: int
    chunks_embedded: int = 0
    duration_seconds: float


class FileNode(BaseModel):
    name: str
    path: str
    type: str  # "file" or "directory"
    size: int = 0
    children: list[FileNode] | None = None


class FileTreeResponse(BaseModel):
    repo_id: str
    root: FileNode
    total_files: int


class FileContentResponse(BaseModel):
    path: str
    content: str
    line_count: int
    last_modified: float


class SymbolInfo(BaseModel):
    name: str
    kind: str  # "function" or "class"
    qualified_name: str | None = None
    file_path: str
    line_start: int
    line_end: int
    complexity: int = 1
    docstring: str | None = None


class SymbolListResponse(BaseModel):
    symbols: list[SymbolInfo]
    total_count: int


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    filter_type: str | None = None
    filter_path: str | None = None


class SearchResultItem(BaseModel):
    chunk_id: str
    file_path: str
    snippet: str
    line_start: int
    line_end: int
    score: float
    match_type: str = "hybrid"


class SearchResponse(BaseModel):
    query: str
    intent: str
    results: list[SearchResultItem]
    total_candidates: int


class AskRequest(BaseModel):
    question: str
    top_k: int = 5
    use_llm: bool = True


class Citation(BaseModel):
    file_path: str
    line_start: int
    line_end: int
    snippet: str = ""
    verified: bool = False


class AskResponse(BaseModel):
    question: str
    answer: str
    citations: list[Citation]
    citation_confidence: float = 0.0
    intent: str = "general"
    model_used: str = "none"
    chunks_retrieved: int = 0
    latency_ms: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class GraphNode(BaseModel):
    id: str
    label: str
    type: str  # "internal", "external"
    pagerank: float = 0.0
    is_orphan: bool = False


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str  # "internal", "external"


class GraphDataResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    cycles: list[list[str]]
    orphans: list[str]
    pagerank_leaderboard: list[dict[str, Any]]


class ImpactResponse(BaseModel):
    target: str
    found: bool
    kind: str  # "module", "symbol", "unknown"
    direct_importers: list[str]
    transitive_dependents: list[str]
    pagerank: float = 0.0
    complexity: int = 0
    callers: list[dict[str, Any]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class MetricScores(BaseModel):
    hit_rate_at_1: float
    hit_rate_at_5: float
    mrr_at_5: float
    avg_latency_ms: float


class EvaluationResponse(BaseModel):
    status: str
    dataset_size: int
    dense: MetricScores
    sparse: MetricScores
    hybrid: MetricScores
