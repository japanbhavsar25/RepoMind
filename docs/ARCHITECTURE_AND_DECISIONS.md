# RepoMind Architecture & Technical Decisions

RepoMind is a code intelligence platform and Retrieval-Augmented Generation (RAG) engine that helps engineers navigate, understand and safely change unfamiliar Python codebases. The hosted demo runs on Vercel (UI) + Render free tier (API) with Groq for generation; the same code runs fully offline with Ollama.

This document details the system architecture, component boundaries, data structures, retrieval algorithms, and engineering trade-offs of RepoMind v2.0.

---

## 1. System Overview

```
                                      +------------------------------------+
                                      |          Web UI (React 19)         |
                                      |    Vite + TypeScript + Tailwind    |
                                      +-----------------+------------------+
                                                        |
                                                        | REST API (HTTP/JSON)
                                                        v
+-----------------------+             +------------------------------------+
|  Typer / Rich CLI     |             |       FastAPI Backend Server       |
|  repomind <command>   |             |       backend/main.py (:8001)      |
+-----------+-----------+             +-----------------+------------------+
            |                                           |
            +-------------------+   +-------------------+
                                |   |
                                v   v
               +------------------------------------+
               |        RepoMind Core Pipeline      |
               +-----------------+------------------+
                                 |
       +-------------------------+-------------------------+
       |                         |                         |
       v                         v                         v
+--------------+          +--------------+          +--------------+
|   Stage 1    |          |   Stage 2    |          |   Stage 3    |
| AST Parsing  |          | Chunking &   |          | Hybrid Search|
| & Discovery  |          | Embedding    |          | RRF (k=60)   |
+-------+------+          +-------+------+          +-------+------+
        |                         |                         |
        |                         |                         |
        v                         v                         v
+--------------+          +--------------+          +--------------+
|   Stage 4    |          |   Stage 5    |          |   Stage 6    |
| Grounded Q&A |          | NetworkX     |          | Git Hotspots |
| & Citations  |          | Blast Radius |          | & Dashboard  |
+--------------+          +--------------+          +--------------+
        |                         |                         |
        +-------------------------+-------------------------+
                                 |
                                 v
               +------------------------------------+
               |         Local Storage Layer        |
               |  - SQLite (.repomind.db + FTS5)    |
               |  - ChromaDB (.repomind_chroma/)    |
               +------------------------------------+
```

---

## 2. Six-Stage Pipeline Architecture

### Stage 1: File Discovery, Delta Hashing & Static AST Parsing
- **Location:** `repomind/utils.py`, `repomind/parser.py`, `repomind/database.py`
- **Mechanism:**
  - Traverses the target repository recursively, filtering out `.gitignore` patterns, virtual environments (`.venv`, `env`), caches (`__pycache__`, `.pytest_cache`), and build artifacts.
  - Computes a deterministic **SHA-256 digest** for each file. On incremental re-indexing, files whose digest matches the database are skipped with zero parsing overhead.
  - Uses Python's native `ast.parse()` to construct an Abstract Syntax Tree:
    - **Classes:** Records class names, line numbers, docstrings, and base class inheritances.
    - **Functions & Methods:** Records name, line numbers, parameters, return type annotations, docstrings, and parent class name (for methods).
    - **Cyclomatic Complexity:** Evaluates decision branches statically by traversing each function's AST subtree and counting branching nodes (`If`, `For`, `AsyncFor`, `While`, `ExceptHandler`, `With`, `Assert`, and Boolean operators in `BoolOp`) plus 1.
    - **Symbol Call Graph:** Inspects `ast.Call` nodes to extract caller-to-callee relationships (`symbol_calls`), tracking the caller file, caller symbol, called function name, and line number.
    - **Imports:** Records module imports (`import os`) and from-imports (`from database import db`), resolving relative dots to absolute module paths.

### Stage 2: Symbol-Aware Chunking, FTS5 & Vector Embeddings
- **Location:** `repomind/chunking.py`, `repomind/embedder.py`, `repomind/database.py`
- **Mechanism:**
  - Rather than naive fixed-character splitting which breaks functions in half, `chunking.py` chunks code strictly along AST symbol boundaries.
  - Every function and class constitutes an isolated semantic chunk enriched with context metadata:
    ```
    # File: orders.py | Symbol: OrderService.checkout (Lines 24-52)
    ```
  - Any remaining non-symbol code (module-level definitions, constants, script bodies) is chunked with a sliding line window with configurable overlap.
  - **FTS5 Sparse Indexing:** Chunks are written directly into an SQLite `fts_chunks` virtual table using BM25 token weighting. This eliminates rebuilding an in-memory BM25 index on every query.
  - **ChromaDB Dense Indexing:** Chunks are vectorized with `all-MiniLM-L6-v2` (384-d) and stored in ChromaDB. Two interchangeable runtimes produce the same vectors: sentence-transformers (PyTorch, when the `[ml]` extra is installed) or ChromaDB's bundled ONNX Runtime model (used in the 512 MB deployment, with the ONNX memory arena disabled and batches of 8). Models load lazily, once per process, and the web server warms them up at startup.

### Stage 3: Code-Aware Two-Stage Hybrid Retrieval
- **Location:** `repomind/hybrid.py`, `repomind/utils.py`
- **Mechanism:**
  - **Code-Aware Tokenization:** Query strings are split by camelCase, PascalCase, snake_case, and dot-separated paths into both the composite identifier and constituent sub-tokens (e.g., `calculateTax` -> `["calculatetax", "calculate", "tax"]`) while stripping standard Python keywords.
  - **Query Intent Classifier:**
    - Identifiers containing `_`, camelCase casing, quotation marks, or `.py` file paths trigger **Code Search Mode** (boosting BM25 lexical weight).
    - Natural language queries (e.g., "how does inventory deduction work?") activate **Balanced Hybrid Mode**.
  - **Reciprocal Rank Fusion (RRF):**
    Sparse ranking ($R_{sparse}$) from SQLite FTS5 (or rank-bm25 fallback) and dense ranking ($R_{dense}$) from ChromaDB cosine similarity are fused using the formula:
    $$RRF\_Score(d) = \frac{w_{dense}}{k + \text{rank}_{dense}(d)} + \frac{w_{sparse}}{k + \text{rank}_{sparse}(d)}$$
    where the smoothing constant $k = 60$.
  - **Cross-Encoder / Heuristic Reranker:** Top candidates are optionally reranked by symbol-name overlap and exact substring matching, pushing exact function/class declarations above indirect comments.

### Stage 4: Grounded Q&A Engine & Citation Verification
- **Location:** `repomind/rag.py`, `repomind/llm.py`
- **Mechanism:**
  - **Evidence Synthesis:** Assembles retrieved chunks into a prompt bounded by strict instructions: every claim must be grounded in provided context using the syntax `[file:start_line-end_line]`.
  - **Dual Mode Operation:**
    1. **Groq (hosted demo):** used when `GROQ_API_KEY` is set (`openai/gpt-oss-120b` by default). Only the retrieved snippets are sent. Each answer reports latency and token counts.
    2. **Local LLM (Ollama):** queries a local Ollama model over HTTP. Nothing leaves the machine.
    3. **Evidence-only fallback:** with no LLM configured, returns the retrieved chunks and their citations without generated prose.
  - **Deterministic Citation Verifier:** Uses regular expressions to extract all `[path:start-end]` citations from the response. Validates each against the SQLite `files` table and chunk line boundaries. Computes a Groundedness Confidence Score (0-100%) and flags unverified or out-of-bounds citations.

### Stage 5: Dependency Graph, PageRank & Downstream Blast-Radius Analysis
- **Location:** `repomind/graph_builder.py`
- **Mechanism:**
  - Constructs a directed graph $G = (V, E)$ using NetworkX where nodes $V$ represent internal modules and external libraries, and directed edges $E = (u, v)$ represent module $u$ importing module $v$.
  - **Criticality Metrics:**
    - **PageRank:** Computes PageRank centrality ($\alpha=0.85$) across internal dependencies. Modules with high PageRank (e.g., `models.py`, `database.py`) represent foundational infrastructure.
    - **Cycle Detection:** Runs Tarjan's strongly connected components algorithm to isolate circular import loops (`simple_cycles`).
    - **Orphan Detection:** Identifies nodes with zero in-degree and zero out-degree within the internal dependency graph (e.g., dead code or unlinked background workers).
  - **Downstream Blast-Radius Analysis:**
    - Given a target file or symbol, inverts the directed graph and executes a breadth-first search (BFS) to identify all transitive dependents that could break if the target changes.
    - Blends PageRank centrality, caller call sites, and cyclomatic complexity to assess modification risk.

### Stage 6: High-Speed Git Telemetry & Interactive Visualizations
- **Location:** `repomind/git_analyzer.py`, `repomind/report.py`
- **Mechanism:**
  - Extracts Git log churn history using optimized streaming `git log --name-only` queries.
  - Computes a normalized **Hotspot Risk Score** ($0-100$) combining:
    - Revision churn frequency (how often a file changes).
    - Code size / cyclomatic complexity.
    - Recency of modifications.
  - Identifies **Ghost Files** (>180 days without commits) and **Bus Factor** (files with >85% commits authored by a single contributor).
  - Generates interactive HTML dashboards using PyVis (physics-based force-directed graph) and Jinja2 templates.

---

## 3. Database Schema

RepoMind persists repository metadata in SQLite (`.repomind.db`) with `PRAGMA foreign_keys = ON;`:

```sql
CREATE TABLE files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    sha256 TEXT NOT NULL,
    lines INTEGER NOT NULL,
    last_indexed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE functions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    line_start INTEGER NOT NULL,
    line_end INTEGER NOT NULL,
    cyclomatic_complexity INTEGER DEFAULT 1,
    docstring TEXT,
    args TEXT,
    returns TEXT,
    parent_class TEXT
);

CREATE TABLE classes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    line_start INTEGER NOT NULL,
    line_end INTEGER NOT NULL,
    docstring TEXT,
    bases TEXT
);

CREATE TABLE imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    module TEXT NOT NULL,
    imported_names TEXT
);

CREATE TABLE symbol_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    caller_file TEXT NOT NULL,
    caller_symbol TEXT NOT NULL,
    callee_name TEXT NOT NULL,
    line_number INTEGER NOT NULL
);

-- Persistent SQLite FTS5 Virtual Table for Sparse BM25
CREATE VIRTUAL TABLE fts_chunks USING fts5(
    chunk_id UNINDEXED,
    file_path UNINDEXED,
    symbol_name,
    content,
    tokenize = 'porter unicode61'
);
```

---

## 4. Key Architectural Decisions & Trade-Offs

| Decision | Alternative Considered | Rationale & Trade-Off |
|---|---|---|
| **Python Standard `ast` over Tree-sitter** | Tree-sitter, Pygments, Regex | Zero external C compiler/binary wheel dependencies; standard library reliability; perfect compatibility across Windows/macOS/Linux. (Trade-off: Python-only static parsing in v2.0). |
| **Reciprocal Rank Fusion ($k=60$)** | Linear Score Combination ($\alpha \cdot \text{dense} + \beta \cdot \text{sparse}$) | BM25 scores (unbounded positive reals) and cosine similarities ($-1$ to $1$) have completely different distributions. Normalizing them requires ad-hoc calibration. RRF depends purely on ranked positions and is robust against distribution shifts. |
| **SQLite FTS5 + ChromaDB Hybrid** | Single Vector Database, Pure Lucene/Elasticsearch | Vector DBs struggle with exact identifier search (`calculate_tax`); keyword search struggles with conceptual questions ("how are errors handled?"). Hybrid indexing combines the strengths of both without heavy JVM or server dependencies. |
| **Pluggable LLM (Groq / Ollama / none)** | One mandatory cloud LLM | Groq gives fast, free-tier generation for the public demo; Ollama keeps code fully local; evidence-only mode still works with no LLM at all. |
| **ONNX Runtime instead of PyTorch for the deployment** | sentence-transformers on PyTorch | Same embedding model, but peak memory fell from 938 MB to 315 MB, so it fits a free 512 MB instance. Trade-off: no cross-encoder reranker there (lexical fallback), and slower indexing on 0.1 vCPU. |
| **FastAPI + React 19 / Vite** | Monolithic Jinja2 SSR, Streamlit | Enables clean REST API separation, strongly typed frontend interfaces, instant HMR development, and interactive client-side graph explorations. |
| **Strict Path Traversal Boundary** | Direct `open(path)` | Repositories must be treated as untrusted input. `resolve_safe_path` prevents directory escape attacks via `../` or malicious symlinks. |
