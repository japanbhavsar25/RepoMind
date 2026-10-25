# RepoMind

**Ask questions about any Python GitHub repo and get answers that cite exact `file:line` ranges, each one checked against the parsed source.**

### 👉 [Live demo: repo-mind-steel.vercel.app](https://repo-mind-steel.vercel.app/)

> The backend runs on Render's free tier and sleeps after 15 idle minutes. The first visit can take **about a minute** to wake it (the page shows a "waking up" message). After that, answers take about 5–8 s.

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-blue?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![Tests](https://img.shields.io/badge/tests-128%20passing-success)](tests/)

---

## What it does

1. **Paste a public GitHub link.** RepoMind shallow-clones it, parses every Python file with `ast`, and builds a symbol table, call graph, import graph, keyword index (SQLite FTS5) and vector index (ChromaDB).
2. **Ask a question in plain English.** It retrieves the most relevant functions and classes and asks an LLM (Groq `openai/gpt-oss-120b`) to answer **only** from them.
3. **Every citation is verified.** Each `[path/file.py:start-end]` in the answer is checked against the parsed source and the retrieved chunks, and the answer shows a "% verified" score.
4. **See the structure.** It also shows the dependency graph with PageRank "important files", import cycles, orphan files, and the **blast radius** of a change (everything that depends on a file, directly or transitively).

The demo comes with three repos already indexed: [`pallets/itsdangerous`](https://github.com/pallets/itsdangerous), a small sample e-commerce service, and **RepoMind's own code**, so you can ask RepoMind how RepoMind works.

---

## Architecture

```
 Browser
   │
   ▼
 Vercel (free) ── React 19 + TypeScript + Tailwind SPA
   │  HTTPS / JSON  (VITE_API_URL)
   ▼
 Render (free, 512 MB Docker) ── FastAPI
   │
   ├─ POST /api/repos/github ─► git clone --depth 1 (HTTPS allow-list, timeout, no prompts)
   │                              │
   │                              ▼
   │                         Python `ast` parser ─► symbols, calls, imports
   │                              │
   │                ┌─────────────┴──────────────┐
   │                ▼                            ▼
   │        SQLite + FTS5 (BM25)        ChromaDB (cosine)
   │        files/functions/classes     all-MiniLM-L6-v2 embeddings
   │                                    via ONNX Runtime (no PyTorch)
   │
   ├─ POST /api/ask ─► hybrid retrieval (vector + BM25, Reciprocal Rank Fusion k=60)
   │                     ─► rerank ─► grounded prompt ─► Groq LLM
   │                     ─► citation verifier ─► answer + "% verified"
   │
   └─ /api/graph, /api/impact ─► NetworkX: PageRank, cycles, orphans, reverse-BFS blast radius
```

The same code also runs fully offline on a laptop, with a local [Ollama](https://ollama.com) model instead of Groq, through the web app, a Typer CLI, or an MCP server.

---

## Measured results

All numbers below were measured on this codebase in October 2026. The retrieval script is [`eval/run.py`](eval/run.py) and its output is in [`eval/results.md`](eval/results.md).

### Retrieval quality
Benchmark: 20 hand-labelled questions about RepoMind's own code (64 files, 500 chunks). A hit means the expected file appears in the top-k results.

| Retrieval setup | Hit@5 | MRR@5 |
|---|---|---|
| Vector only | 0.85 | 0.70 |
| Hybrid (vector + BM25, RRF) | 0.80 | 0.56 |
| Hybrid + cross-encoder rerank | 0.85 | 0.67 |
| **Hybrid + lexical rerank (live demo setup)** | **0.85** | **0.70** (Hit@1 0.60) |

**What this shows:** on these natural-language questions, BM25 fusion on its own *hurt* ranking, because test files share a lot of vocabulary with the code they test. Reranking recovered the loss. This gold set has no identifier-style queries (like `verify_citations`), which is where keyword search should help most. Adding them is on the list.

### Deployment and cost
| Metric | Result |
|---|---|
| Peak memory (startup + clone + index + answer) | **938 MB → 315 MB (−66%)** after replacing PyTorch with ONNX Runtime and turning off its memory arena, so it fits Render's free 512 MB |
| Answer time on the live free tier (warm) | 4.7–8.2 s end to end, of which the Groq call is 0.8–2.4 s |
| Tokens per answer | about 1.3k–3.1k (prompt + completion) |
| Indexing a new repo | about 15 s on a laptop CPU for `itsdangerous` (154 chunks); a few minutes on Render's free 0.1 vCPU |
| Search latency (laptop CPU) | about 0.2 s per query |

---

## Key design decisions

- **Chunk by symbol, not by token count.** Functions and classes come from the AST with exact line ranges, so every retrieved chunk maps to a citable `file:start-end`.
- **Verify, don't trust.** The LLM is told to cite every claim with a full path. A verifier then parses the citations and checks them against SQLite and the retrieved chunks. Citations it can't match lower the "% verified" score instead of being hidden.
- **Prompt-injection guard.** Retrieved code is fenced as context, and the system prompt says never to follow instructions found inside it.
- **Built for 512 MB.** Embeddings run on ChromaDB's bundled ONNX MiniLM, the same model as sentence-transformers, so the vectors are compatible. The cross-encoder reranker is optional and falls back to a lexical heuristic when PyTorch isn't installed. Models are loaded once and warmed up at startup.
- **Safe to expose publicly.** In `PUBLIC_MODE`, registering server-side folders is disabled and GitHub clones are rate-limited per IP (5 per hour). Clone URLs are HTTPS-only with a host allow-list (github.com, gitlab.com, bitbucket.org). Clones are shallow, non-interactive, time-limited, and symlinks are turned off. File reads are confined to the repo root. Repository code is parsed, never executed.

---

## Limitations

- Python only; other languages are skipped.
- Static analysis only: dynamic dispatch, reflection and runtime imports aren't resolved.
- On the free tier, indexing a large repo is slow, and anything added by visitors disappears when the server restarts. Only the three demo repos are built into the image.
- The retrieval benchmark is small (20 questions on one repo). Treat the numbers as a regression check, not a general score.

---

## Run it locally

Requires Python 3.11+, Node 18+ and git.

```bash
git clone https://github.com/japanbhavsar25/RepoMind.git
cd RepoMind
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"            # server + ML extras + test tools
```

Pick an LLM: put `GROQ_API_KEY=gsk_...` in a `.env` file (free key from [console.groq.com](https://console.groq.com)), **or** run [Ollama](https://ollama.com) locally (`ollama pull phi3`). With neither, RepoMind still returns the retrieved evidence, just without a written answer.

```bash
# Terminal 1: API on :8001 (the Vite dev server proxies /api there)
uvicorn backend.main:app --port 8001 --reload

# Terminal 2: web UI on :5173
cd frontend && npm install && npm run dev
```

Run the tests: `pytest` (128 tests) and `ruff check repomind backend tests`.

### CLI
```bash
repomind index .                 # parse ASTs into SQLite
repomind embed                   # build the vector index
repomind ask "Where are citations verified?"
repomind impact repomind/rag.py  # blast radius before a refactor
repomind graph . --open          # interactive dependency graph
repomind evaluate                # retrieval benchmark
repomind mcp                     # MCP server for Claude / Cursor
```

### Deploy your own (free)
- **Backend:** in Render, choose New → Blueprint, pick this repo ([`render.yaml`](render.yaml)), and set `GROQ_API_KEY`.
- **Frontend:** import the repo in Vercel with **Root Directory = `frontend`**, and set the backend URL in [`frontend/.env.production`](frontend/.env.production).

---

## More docs
[Architecture & decisions](docs/ARCHITECTURE_AND_DECISIONS.md) · [Testing & evaluation](docs/TESTING_AND_EVALUATION.md) · [Security & limitations](docs/SECURITY_AND_LIMITATIONS.md) · [Deployment](docs/DEPLOYMENT.md)

## License
[MIT](LICENSE) © 2026 Japan Bhavsar
