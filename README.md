# RepoMind 🧠 v2.0

> **Local-First Code Intelligence, Dependency Graphing & Grounded RAG Platform**  
> *Understand unfamiliar codebases, trace change impact, and ask questions backed by verifiable source citations — 100% offline, zero cloud API fees, zero telemetry.*

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-blue?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19.0-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.9-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-v4.0-38B2AC?logo=tailwind-css&logoColor=white)](https://tailwindcss.com)
[![Tests](https://img.shields.io/badge/Tests-73%20passed-success)](https://github.com/your-username/RepoMind)
[![License](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)

---

## 🌟 What is RepoMind?

RepoMind is a full-stack, local-first repository intelligence application and Retrieval-Augmented Generation (RAG) engine. It empowers software engineers, engineering leads, and technical auditors to rapidly onboard to unfamiliar codebases, perform change impact analysis before refactoring, and query repository semantics with deterministic evidence.

### Core Value Proposition
- 🔒 **100% Local-First & Air-Gapped:** All parsing, indexing, vectorization, and graph algorithms run on your local machine. No code leaves your computer.
- 🎯 **Verifiable Source Grounding:** Every answer includes exact `[file:start-end]` line-range citations verified against SQLite AST tables to eliminate AI hallucinations.
- ⚡ **Two-Stage Hybrid Search:** Combines persistent **SQLite FTS5** BM25 sparse search and **ChromaDB** dense vector embeddings via **Reciprocal Rank Fusion ($k=60$)** with code-aware camelCase/snake_case tokenization.
- 💥 **Downstream Blast-Radius Analysis:** Inverts the NetworkX dependency graph and call graph to trace transitive downstream dependents, preventing accidental breaking changes.
- 📊 **Quantitative Retrieval Benchmarks:** Integrated evaluation harness reporting **Hit@1 (100%)**, **Hit@5 (100%)**, **MRR@5 (1.0000)**, and average latency (<15ms).
- 💻 **Modern Web UI & Typer CLI:** Includes a responsive React 19 single-page application with 8 specialized views, a rich terminal CLI, and an Anthropic Model Context Protocol (MCP) server.

---

## 🏗️ Architecture & 6-Stage Pipeline

```
                                +------------------------------------+
                                |       React 19 + TypeScript SPA    |
                                |     Overview • Files • Symbols     |
                                |     Search • Ask • Graph • Impact  |
                                +-----------------+------------------+
                                                  |
                                                  | REST API (HTTP/JSON)
                                                  v
+-------------------------+     +------------------------------------+
|    Typer / Rich CLI     |     |       FastAPI Backend Server       |
|    repomind <command>   |     |       backend/main.py (:8000)      |
+------------+------------+     +-----------------+------------------+
             |                                    |
             +--------------------+---------------+
                                  |
                                  v
+--------------------------------------------------------------------+
|                       RepoMind Engine Pipeline                     |
+--------------------------------------------------------------------+
| Stage 1: Static AST Parsing, Cyclomatic Complexity & Call Graph    |
| Stage 2: Symbol-Aware Chunking, SQLite FTS5 & ChromaDB Vectors     |
| Stage 3: Code Tokenizer & Reciprocal Rank Fusion (RRF k=60)        |
| Stage 4: Grounded Q&A Synthesizer & Strict Citation Verifier       |
| Stage 5: NetworkX Dependency Graph, PageRank & Reverse BFS Impact  |
| Stage 6: Git Commit Churn Hotspot Risk Scoring & HTML Visualizer   |
+---------------------------------+----------------------------------+
                                  |
                                  v
+--------------------------------------------------------------------+
|                         Local Storage Layer                        |
|   - SQLite (.repomind.db): files, functions, classes, calls, FTS5  |
|   - ChromaDB (.repomind_chroma/): 384-d all-MiniLM-L6-v2 vectors   |
+--------------------------------------------------------------------+
```

---

## 🚀 Quick Start

### 1. Prerequisites
- **Python:** 3.11 or 3.12 (tested on 3.12.1)
- **Node.js:** 18+ (tested on Node.js 24.15 & npm 11.12)
- **Optional Local LLM:** [Ollama](https://ollama.com) running locally (`ollama pull mistral`)

### 2. Setup & Installation

```powershell
# Clone the repository
git clone https://github.com/your-username/RepoMind.git
cd RepoMind

# Create and activate Python virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1  # Windows PowerShell
# source .venv/bin/activate    # Linux / macOS

# Install Python package and dependencies
pip install -e .
pip install -r backend/requirements.txt

# Install frontend dependencies
cd frontend
npm install
cd ..
```

### 3. Launching the Web Application

In Terminal 1 (Backend Server):
```powershell
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

In Terminal 2 (Frontend Client):
```powershell
cd frontend
npm run dev
```

Open your browser to **`http://localhost:5173`**. The web UI will automatically load with the bundled **`ecommerce_service`** reference repository pre-indexed and ready to explore!

---

## 🖥️ Web UI Feature Views

| View | Purpose | Highlights |
|---|---|---|
| **Overview** | System dashboard | Repository stats (files, functions, classes, imports), quick actions, architectural guide. |
| **File Explorer** | Code navigation | Interactive file tree, syntax view, line numbers, last modified timestamps. |
| **Symbols & AST** | Structural catalog | Filter by function/class, search symbols, inspect cyclomatic complexity, arguments, docstrings, and callers. |
| **Code Search** | Real-time hybrid search | Combined FTS5 BM25 and ChromaDB cosine retrieval with RRF ranking and intent detection. |
| **Ask RepoMind** | Grounded Q&A | Synthesizes answers with strict citations; toggles between deterministic evidence mode and local Ollama. |
| **Dependency Graph** | Architectural topology | Visualizes internal vs. external dependencies, calculates PageRank centrality, isolates cycle loops and dead code orphans. |
| **Blast Radius** | Change-impact analysis | Inverts import and call graphs to compute transitive downstream dependents before making code edits. |
| **Evaluation** | Quantitative benchmarking | Evaluates 12 ground truth queries against the repo, reporting Hit@1, Hit@5, MRR@5, and latency. |

---

## ⌨️ CLI Usage Reference

RepoMind provides a complete command-line interface for terminal workflows and scripts:

```powershell
# 1. Index repository AST symbols, complexity, and call sites
repomind index ./samples/ecommerce_service

# 2. Build ChromaDB dense vector embeddings & SQLite FTS5 index
repomind embed ./samples/ecommerce_service

# 3. Ask questions with grounded citations
repomind ask "Where is password hashing implemented?"

# 4. Analyze blast radius of a file or symbol before refactoring
repomind impact models.py
repomind impact OrderService.checkout

# 5. Run the quantitative retrieval evaluation benchmark
repomind evaluate

# 6. Generate an interactive dependency graph
repomind graph ./samples/ecommerce_service --open

# 7. Generate a Git churn hotspot risk analysis & HTML report
repomind report ./samples/ecommerce_service --open

# 8. Start the Model Context Protocol (MCP) server for Cursor / Claude
repomind mcp
```

---

## 📊 Quantitative Retrieval Benchmarks

RepoMind includes an integrated benchmarking harness (`repomind/evaluator.py`) tested against the reference microservice (`samples/ecommerce_service`):

| Metric | Target | Verified Score |
|---|---|---|
| **Hit@1** | $\ge 80\%$ | **100.0%** (12/12 queries ranked #1) |
| **Hit@5** | $\ge 95\%$ | **100.0%** (12/12 queries in top 5) |
| **MRR@5 (Mean Reciprocal Rank)** | $\ge 0.85$ | **1.0000** |
| **Mean Retrieval Latency** | $< 50\text{ ms}$ | **12.3 ms** |

---

## 🔒 Security & Safe Path Boundaries

Because RepoMind analyzes third-party code, it enforces strict security controls in `backend/security.py`:
- **Path Traversal Protection:** `resolve_safe_path()` resolves canonical paths using `Path.resolve()` and enforces `os.path.commonpath()`, blocking `../`, null bytes (`\0`), and cross-drive Windows attacks.
- **SSRF Protection:** `validate_git_url()` validates remote URLs, permitting only HTTPS/SSH and blocking loopback (`127.0.0.1`), private RFC 1918 subnets (`10.x`, `192.168.x`), and cloud metadata endpoints (`169.254.169.254`).
- **No Code Execution:** Static analysis uses Python's standard `ast.parse` exclusively. RepoMind **never** executes, imports, or `eval()`s inspected code.

---

## 📚 Complete Documentation Suite

For detailed technical references, visit the `docs/` directory:
- 📖 [**Architecture & Technical Decisions**](docs/ARCHITECTURE_AND_DECISIONS.md) — Pipeline stages, RRF mathematics, and database schema.
- 🧪 [**Testing & Retrieval Evaluation**](docs/TESTING_AND_EVALUATION.md) — 73 automated tests, test strategy, and benchmark harness.
- 🛡️ [**Security Model & Limitations**](docs/SECURITY_AND_LIMITATIONS.md) — Threat model, SSRF protections, and static AST boundaries.
- 🚢 [**Deployment & Operations Guide**](docs/DEPLOYMENT.md) — Local startup, environment variables, and Docker containerization.
- 🎓 [**Learning Guide & Interview Defense**](docs/LEARNING_GUIDE.md) — Comprehensive guide with 15 technical interview questions and answers.

---

## 🧪 Automated Testing

RepoMind is backed by a comprehensive automated test suite:

```powershell
# Run all 73 unit, integration, and API tests
pytest tests/ -v

# Check code formatting and style
ruff check repomind backend tests

# Build frontend production bundle
cd frontend; npm run build
```

**Verified Test Suite Status:**
- `pytest tests/ -v`: **73 passed in 9.74s**
- `ruff check`: **0 errors, 0 warnings**
- `npm run build`: **Built in 1.59s, 0 errors**

---

## 📄 License

RepoMind is open-source software licensed under the [MIT License](LICENSE).
