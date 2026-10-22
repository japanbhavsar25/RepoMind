# RepoMind 🧠

> Ask your Python codebase questions. Get answers. Completely free. Runs locally.

[![CI](https://github.com/YOUR_USERNAME/repomind/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/repomind/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Version](https://img.shields.io/badge/version-2.0.0-green)

## What It Does

RepoMind reads your Python project, builds a knowledge graph, and lets you ask natural-language questions about your code using only free, local tools. No telemetry, no API keys, no data leaves your machine.

| Feature | Command | Description |
|---------|---------|-------------|
| **Index** | `repomind index .` | Parse all `.py` files into SQLite with AST complexity & call graph |
| **Embed** | `repomind embed` | Convert code into semantic vectors & SQLite FTS5 sparse index |
| **Ask** | `repomind ask "..."` | Grounded local LLM answers with citation verification badge |
| **Impact** | `repomind impact <target>` | Downstream blast-radius, cyclomatic complexity & caller graph |
| **Evaluate** | `repomind evaluate` | Quantitative benchmark comparing Dense vs. Sparse vs. Hybrid RRF |
| **MCP Server** | `repomind mcp` | stdio Model Context Protocol server for AI IDEs (Cursor, Claude) |
| **Graph** | `repomind graph .` | Interactive dependency graph (HTML) |
| **Report** | `repomind report .` | Architecture Health Score, Composite Hotspots & Bus Factor |
| **Search** | `repomind search login` | Find functions/classes by name |
| **Stats** | `repomind stats` | Quick overview of indexed repository |

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Parser | Python `ast` | Built-in, zero dependencies, precise |
| Database | SQLite | Single file, zero setup |
| Embeddings | `sentence-transformers` (all-MiniLM-L6-v2) | 22MB, CPU-friendly, free |
| Vector DB | ChromaDB | Local persistence, no server |
| LLM | Ollama (Phi-3) | Runs entirely on your machine, $0 cost |
| Graph | NetworkX + PyVis | Pure Python, interactive HTML output |
| Git Analysis | GitPython | Mines commit history for hotspots |
| CLI | Typer + Rich | Beautiful terminal UI |

## Prerequisites

- **Python 3.11+**
- **[Ollama](https://ollama.com)** — free local LLM (download and keep running)

## Installation

```powershell
# Clone the repo
git clone https://github.com/YOUR_USERNAME/repomind.git
cd repomind

# Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install in development mode
pip install -e .

# Verify Ollama is running
ollama run phi3
# (Type /bye to exit)
```

## Quick Start

```powershell
# 1. Index your project
repomind index .

# 2. Build embeddings (one-time setup)
repomind embed

# 3. Ask questions
repomind ask "What does the database module do?"
repomind ask "How does authentication work?"

# 4. Generate visualizations
repomind graph .
repomind report .

# 5. Quick search
repomind search login
repomind stats
```

## Architecture

```
Your .py files
    │
    ▼
┌─────────────────┐     ┌──────────────────┐
│  Python ast     │────▶│   SQLite DB      │
│  (parser.py)    │     │  (.repomind.db)  │
└─────────────────┘     └──────────────────┘
    │                         │
    ▼                         ▼
┌─────────────────┐     ┌──────────────────┐
│  sentence-      │     │  ChromaDB        │
│  transformers   │     │  (.repomind_     │
│  (embedder.py)  │     │   chroma/)       │
└─────────────────┘     └──────────────────┘
    │                         │
    └──────────┬──────────────┘
               ▼
      ┌─────────────────┐
      │  Ollama (local) │
      │  Phi-3 /        │
      │  CodeLlama      │
      └─────────────────┘
               │
               ▼
      ┌─────────────────┐
      │  Typer + Rich   │
      │  CLI            │
      └─────────────────┘
               │
               ▼
      ┌─────────────────┐
      │  PyVis HTML     │
      │  Jinja2 Report  │
      └─────────────────┘
```

## How It Works

### 1. Index — Parse Your Code
Reads every `.py` file using Python's built-in `ast` module. Extracts:
- Functions, classes, methods
- Import statements
- Docstrings and line numbers
- File metadata (size, modification time)

Stores everything in a local SQLite database (`.repomind.db`).

### 2. Embed — Semantic Search
Converts code and docstrings into 384-dimensional vectors using `all-MiniLM-L6-v2`. Stores these in ChromaDB.

This enables **semantic search**: searching by meaning, not just exact words. "Login" will match `authenticate_user()`.

### 3. Ask — RAG Pipeline
When you ask a question:
1. Your question is converted to a vector
2. Top-5 most similar code chunks are retrieved from ChromaDB
3. A prompt is built: "Here is some code. Now answer..."
4. The prompt is sent to your local Ollama LLM
5. You get a contextual, accurate answer

### 4. Graph — Dependency Map
Builds a directed graph from import statements:
- **Green edges** = internal imports (your code)
- **Red edges** = external imports (third-party libraries; stdlib is excluded to reduce noise)
- **Node size** = PageRank importance
- **Node color** = Git activity (red = hot, blue = stable)

### 5. Report — Analytics Dashboard
Generates a dark-themed HTML report with:
- Repository stats (files, functions, classes)
- Hotspot files (most changed = riskiest)
- Ghost files (not touched in 6+ months)
- Orphan files (no internal dependencies)
- Circular dependencies
- Top important files by PageRank

## Project Structure

```
repomind/
├── __init__.py          # Package version
├── cli.py               # Typer CLI commands (index, embed, ask, graph, report, search, stats)
├── database.py          # SQLite storage layer with schema
├── parser.py            # AST-based code extractor
├── embedder.py          # Sentence transformer embeddings
├── rag.py               # Retrieval-Augmented Generation pipeline
├── llm.py               # Ollama HTTP client
├── graph_builder.py     # NetworkX dependency graph + PageRank
├── git_analyzer.py      # Git history mining for hotspots
├── report.py            # HTML dashboard generator (Jinja2 + PyVis)
└── utils.py             # File system helpers

tests/
├── test_parsers.py       # AST parser tests
├── test_database.py      # Storage layer tests
├── test_graph_builder.py # Dependency graph tests
└── test_cli.py           # CLI integration tests
```

## Commands Reference

```powershell
# Index a project
repomind index C:\Projects\MyApp

# Build embeddings (uses the built-in all-MiniLM-L6-v2 model)
repomind embed

# Ask a question
repomind ask "How does the auth flow work?" --top-k 5

# Generate dependency graph
repomind graph . --output ./output --open

# Generate full report
repomind report . --output ./output --open

# Search by name
repomind search database

# Show stats
repomind stats
```

## Why I Built This

Traditional code search tools use regex or text matching. They fail when:
- You search "login" but the function is called `authenticate_session()`
- You want to understand relationships between files
- You need to identify abandoned or over-changed code

RepoMind solves this with **semantic search** (meaning, not just words) and **graph analysis** (structure, not just text) — all running locally with zero API costs.

## Development

```powershell
# Run tests
pytest tests/ -v

# Lint code
ruff check repomind/

# Build executable
pyinstaller --name repomind --onefile repomind/cli.py
```

## Windows Tips

- Use **Windows Terminal** (not legacy CMD) for best Rich rendering
- If PowerShell blocks scripts: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
- Ollama runs in the system tray — keep it open while using `ask`
- First `embed` run downloads the 22MB model to `~\.cache\torch\sentence_transformers\`

## License

MIT
