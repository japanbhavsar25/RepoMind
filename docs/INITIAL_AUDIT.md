# RepoMind — Initial Project Audit (Phase 0 Baseline)

**Audit Date:** 2026-10-23T02:40:00+05:30  
**Auditor:** Antigravity Senior Engineering System  
**Environment:** Windows 11, Python 3.12.1, Node.js v24.15.0, npm 11.12.1, 8 GB RAM, 512 GB Storage  
**Git Branch:** `master` @ commit `9c3e87f` (`feat: upgrade RepoMind to v2.0 flagship architecture`)

---

## 1. Executive Summary

RepoMind is a local-first Python codebase intelligence tool and RAG engine that provides AST-level structural analysis, dependency graph visualization, Git hotspot telemetry, hybrid search (dense embeddings + SQLite FTS5 sparse search fused via Reciprocal Rank Fusion), citation-grounded Q&A, and an MCP server.

The core analysis engine has been upgraded to v2.0 with 59 passing unit and integration tests. However, it currently exists primarily as a CLI application (`repomind.cli:app`) and an MCP server. It lacks the full-stack web application layer (FastAPI backend service layer, REST endpoints, and a Vite + React + TypeScript + Tailwind CSS web interface) requested by the owner's Master Engineering Specification.

This audit establishes the baseline facts, inventory, strengths, gaps, and an engineering plan to build the web application while preserving 100% of the existing CLI and core library functionality.

---

## 2. Directory Structure & File Inventory

```
d:\RepoMind/
├── .git/                      # Git repository (master @ 9c3e87f)
├── .gitignore                 # Standard Python/IDE ignore list + RepoMind DBs
├── .repomind.db               # SQLite database (741 KB) generated from indexing RepoMind itself
├── .repomind_chroma/          # ChromaDB persistent vector storage (195 chunks)
├── .repomind_data/            # [Untracked] Pre-indexed sample data (.repomind_data/samples/ecommerce/ecommerce.db)
├── .repomind_output/          # Generated HTML reports, video scripts, and presentation slides
├── Dockerfile                 # Container specification
├── pyproject.toml             # Python package manifest (setuptools, repomind v2.0.0)
├── RAG_Textbook.md            # Reference notes on RAG systems
├── README.md                  # Existing documentation for CLI v2.0
├── repomind.ps1               # PowerShell helper script
├── RepoMind_Interview_Guide.pdf # Interview prep guide
├── eval/                      # Retrieval evaluation harness
│   ├── gold.json              # Fixed benchmark query set
│   ├── results.md             # Benchmark metrics
│   └── run.py                 # Evaluation execution script
├── repomind/                  # Core Python engine library
│   ├── __init__.py            # Package root (__version__ = "2.0.0")
│   ├── chunking.py            # AST symbol-aware code chunker
│   ├── cli.py                 # Typer + Rich CLI entrypoint
│   ├── config.py              # Path and runtime configuration
│   ├── database.py            # SQLite schema, CRUD, FTS5 virtual table
│   ├── embedder.py            # Lazy sentence-transformers wrapper (all-MiniLM-L6-v2)
│   ├── evaluator.py           # Quantitative retrieval evaluation (Hit@k, MRR@k, Latency)
│   ├── git_analyzer.py        # Git churn, composite hotspot risk (0-100), bus factor
│   ├── graph_builder.py       # NetworkX import graph, PageRank, cycles, blast radius
│   ├── graphrag.py            # GraphRAG relationship summarization
│   ├── hybrid.py              # Code-aware tokenization, query intent, weighted RRF, CrossEncoder
│   ├── llm.py                 # Ollama REST client
│   ├── mcp_server.py          # stdio Model Context Protocol (MCP) server
│   ├── parser.py              # AST visitor (functions, classes, calls, cyclomatic complexity)
│   ├── pytest.ini             # Pytest config
│   ├── rag.py                 # Retrieval-Augmented Generation, delta sync, citation verification
│   ├── report.py              # Jinja2 + PyVis interactive HTML report generator
│   └── utils.py               # Tokenizer, identifier splitter, stopword filtering, path helpers
└── tests/                     # Automated test suite (59 tests, 100% passing)
    ├── test_chunking.py       # Chunker chunk boundaries and line mappings (3 tests)
    ├── test_cli.py            # Typer CLI invocation and error modes (8 tests)
    ├── test_database.py       # SQLite CRUD, cascades, and search (10 tests)
    ├── test_graph_builder.py  # NetworkX graph, PageRank, cycles, HTML export (10 tests)
    ├── test_hybrid.py         # Tokenizer, RRF math, reranker fallback (3 tests)
    ├── test_parsers.py        # AST function/class extraction, imports, hashing (9 tests)
    ├── test_rag.py            # Chunk indexing, hybrid retrieve, ask prompt (3 tests)
    └── test_v2_features.py    # V2.0 features (FTS5, calls, blast radius, citations, MCP) (13 tests)
```

---

## 3. Technology Stack & Environment

| Layer | Audited Component | Version / Spec | Status |
|-------|-------------------|----------------|--------|
| **OS** | Windows 11 | Build 26100 | Verified |
| **Runtime** | Python | 3.12.1 (64-bit) | Verified |
| **Node.js** | Node.js / npm | v24.15.0 / 11.12.1 | Verified |
| **CLI Framework** | Typer + Rich | typer 0.24.2, rich 15.0.0 | Verified |
| **Database** | SQLite + FTS5 | SQLite 3.45.1 (bundled in Python 3.12) | Verified FTS5 enabled |
| **Vector Store** | ChromaDB | 1.5.8 | Verified |
| **Embeddings** | sentence-transformers | 5.4.1 (all-MiniLM-L6-v2) | Verified, lazy loaded |
| **Graph Engine** | NetworkX | 3.6.1 | Verified |
| **Visualization**| PyVis + Jinja2 | pyvis 0.3.0, jinja2 3.1.6 | Verified with UTF-8 patch |
| **Web Backend** | FastAPI + Uvicorn | fastapi 0.141.1, uvicorn 0.46.0 | Installed, needs app structure |
| **HTTP Clients**| httpx + requests | httpx 0.28.1, requests 2.33.1 | Installed |
| **Frontend** | React + Vite + TS | Not yet initialized | Pending Phase 1-2 |
| **LLM Provider**| Local Ollama | Phi-3 / mistral / llama3 | Verified offline REST client |

---

## 4. Current Feature Implementation Status

### Working & Verified Components (59/59 Tests Pass)
1. **AST Code Parser (`repomind/parser.py`):**
   - Extracts functions, methods, classes, and import statements.
   - Computes Cyclomatic Complexity per function/method across branching opcodes (`If`, `For`, `While`, `With`, `ExceptHandler`, `BoolOp`, etc.).
   - Extracts symbol calls (`caller_file`, `caller_symbol`, `callee_name`, `line_number`).
   - Uses `ParseResult(tuple)` with bytecode-aware unpacking to preserve backward compatibility for legacy 3-tuple unpacking while supporting 4-tuple unpacking for calls.
2. **SQLite Database Layer (`repomind/database.py`):**
   - Tables: `files`, `functions`, `classes`, `imports`, `symbol_calls`, and virtual table `fts_chunks` (FTS5).
   - Foreign key cascades on file deletion.
   - FTS5 BM25 disk-based sparse query execution with fallback to in-memory `rank-bm25`.
3. **Symbol-Aware Chunking (`repomind/chunking.py`):**
   - Chunks code by top-level AST nodes and methods, recording file paths and exact start-end line numbers.
4. **Hybrid Retrieval with RRF (`repomind/hybrid.py`):**
   - Deterministic identifier splitter (`split_identifier`) handling `camelCase`, `PascalCase`, `snake_case`, and dot paths.
   - Code-aware tokenizer stripping Python keywords/stopwords.
   - Query intent detection boosting BM25 weight on exact identifiers.
   - Weighted Reciprocal Rank Fusion ($k=60$).
   - Offline `CrossEncoderReranker` with heuristic lexical-symbol fallback.
5. **RAG Pipeline & Delta Vector Sync (`repomind/rag.py`):**
   - Deterministic chunk deletion from ChromaDB and SQLite FTS5 on file hash change or file removal.
   - Grounded context assembly with `[file:start-end]` formatting.
   - Post-generation citation verification against SQLite files and extracted AST chunks, returning citation confidence scores.
6. **Dependency Graph & Blast Radius (`repomind/graph_builder.py`):**
   - Directed NetworkX graph of module imports.
   - PageRank centrality computation.
   - Circular dependency cycle detection via Johnson's elementary cycles.
   - Orphan file detection (no incoming or outgoing internal edges).
   - Downstream blast-radius computation (`nx.ancestors` over reverse dependency graph).
7. **Git Telemetry & Risk Scoring (`repomind/git_analyzer.py`):**
   - Commit churn tracking.
   - Composite Hotspot Risk score ($0-100$) combining churn (45%), cyclomatic complexity (35%), and PageRank (20%).
   - Bus Factor / Knowledge Silo detection ($\ge 85\%$ single author commits).
8. **Quantitative Evaluation Harness (`repomind/evaluator.py`):**
   - Compares Dense-only, Sparse-only, and Hybrid RRF on Hit@1, Hit@5, MRR@5, and Latency.
9. **MCP Server (`repomind/mcp_server.py`):**
   - Stdio JSON-RPC 2.0 protocol exposing `repomind_search`, `repomind_symbol_lookup`, `repomind_blast_radius`, and `repomind_health_summary`.

### Gaps & Incomplete Work
1. **Web Backend API (`backend/`):**
   - Currently, `backend/` exists as an empty directory structure with `__pycache__` artifacts.
   - Needs a clean FastAPI application (`backend/main.py`), Pydantic schemas (`backend/schemas.py`), configuration (`backend/config.py`), security validation (`backend/security.py`), and modular routers for:
     - Health (`/api/health`)
     - Repository management (`/api/repos`)
     - File browsing & content (`/api/files`)
     - Symbol exploration (`/api/symbols`)
     - Code search (`/api/search`)
     - Grounded Q&A (`/api/ask`)
     - Architecture graph (`/api/graph`)
     - Change-impact analysis (`/api/impact`)
     - Retrieval evaluation (`/api/evaluate`)
2. **Bundled Sample Repository (`samples/ecommerce_service`):**
   - `samples/ecommerce_service` is currently empty.
   - Needs a realistic, multi-file Python microservice with known functions, classes, imports, database operations, auth routines, background tasks, and an intentional orphan file so first-run exploration and automated tests work out of the box with zero external dependencies.
3. **Frontend Application (`frontend/`):**
   - No frontend code exists yet.
   - Needs a responsive, modern Vite + React + TypeScript + Tailwind CSS application covering all required product views (Repository Overview, File Explorer, Code Viewer, Search, Ask RepoMind, Dependency Graph, Impact Analyzer, and Evaluation Dashboard).
4. **Security Hardening:**
   - Need strict path traversal validation (`..`, absolute paths, symlinks).
   - Need Git clone safety controls (disallow shell interpolation, timeout enforcement, URL host whitelist).
5. **Documentation Suite (`docs/`):**
   - Need `docs/STATE.md`, `docs/ARCHITECTURE_AND_DECISIONS.md`, `docs/TESTING_AND_EVALUATION.md`, `docs/SECURITY_AND_LIMITATIONS.md`, `docs/DEPLOYMENT.md`, and `docs/LEARNING_GUIDE.md`.

---

## 5. Hardware, Memory & Environmental Constraints

- **Host RAM:** 8 GB. This requires strict memory discipline:
  - Do NOT load heavy PyTorch models during standard unit tests (use mocked or heuristic fallbacks).
  - Use lazy loading for `sentence-transformers` and `chromadb`.
  - In the web API, maintain bounded chunk batching during indexing.
  - Keep SQLite connections scoped or managed per repository to avoid resource exhaustion.
- **Operating System:** Windows 11.
  - Windows paths use backslashes (`\`); all path handling must use `pathlib.Path` or normalize to POSIX `/` for consistent repository relative paths and URLs.
  - PyVis HTML files must be written with `encoding="utf-8"` to prevent Windows `cp1252` encoding crashes.
  - Subprocess calls (Git, CLI) must never pass unescaped shell strings.

---

## 6. Retention & Architectural Strategy

1. **Retain 100% of `repomind/` Core Library:**
   - The CLI (`repomind.cli`), parsers, database, graph builder, evaluator, and MCP server are mature, tested, and fully functional.
   - The backend service layer will import and reuse `repomind` components directly as a domain engine.
2. **Multi-Repository Data Model:**
   - To support switching between the bundled sample repository and imported repositories, store each repository's SQLite database and ChromaDB collection in a dedicated storage directory:
     `.repomind_data/{repo_id}/{repo_id}.db` and `.repomind_data/{repo_id}/chroma/`.
   - The active repository can be configured or selected per request via a `repo_id` parameter or active session state.
3. **Bundled Sample Microservice (`ecommerce_service`):**
   - Create a clean 8-module sample in `samples/ecommerce_service`:
     - `models.py` (User, Order, Product, Payment dataclasses)
     - `database.py` (DB connection and CRUD)
     - `auth.py` (password hashing, JWT verification)
     - `orders.py` (order placement, inventory check)
     - `payments.py` (payment gateway interface, Stripe/Mock processor)
     - `notifications.py` (email/SMS dispatch)
     - `utils.py` (token generation, currency formatting)
     - `orphan_task.py` (isolated maintenance worker for orphan detection)
4. **FastAPI Web Backend (`backend/`):**
   - Thin routers with Pydantic request/response validation.
   - Modular service layer (`backend/services/`) isolating business logic from web protocols.
   - Strict input validation preventing path traversal and command injection.
5. **Modern React Frontend (`frontend/`):**
   - Scaffolded with Vite + React + TypeScript + Tailwind CSS.
   - Clean, professional engineering dashboard designed for code comprehension and interview demonstrations.

---

## 7. Immediate Next Steps (Phase 1: Stable Foundation)

1. Commit `docs/INITIAL_AUDIT.md` and create `docs/STATE.md`.
2. Construct the bundled `samples/ecommerce_service` Python microservice.
3. Implement `backend/` with FastAPI, Pydantic schemas, repo manager, and routers.
4. Add comprehensive contract and integration tests in `tests/test_api.py`.
5. Run full test suite (`pytest tests/`) and verify 100% passing rate.
