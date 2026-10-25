# RepoMind Testing & Retrieval Evaluation

How RepoMind is tested, and how retrieval quality is measured. Every number here comes from a command you can re-run.

---

## 1. Principles

1. **No made-up numbers.** Pass counts and metrics come from running the commands below.
2. **Offline and keyless tests.** The suite needs no internet, no API keys and no GPU: `git clone` and the Groq API are mocked, and slow embedding is turned off unless a test needs it (see `tests/conftest.py`).
3. **Isolated state.** Tests write repo registrations to a temporary data directory, never to the developer's real `.repomind_data/`.

---

## 2. Test suite: 128 tests

```bash
pytest                                # all tests
ruff check repomind backend tests     # lint
cd frontend && npm run build          # type-check (tsc -b) + production bundle
```

| Test file | Tests | Covers |
|---|---|---|
| `test_parsers.py` | 10 | AST extraction of functions/classes/imports, hashing, file discovery (skips hidden and build folders inside a repo) |
| `test_database.py` | 9 | SQLite schema, upserts, cascades, search |
| `test_chunking.py` | 3 | Symbol-aware chunk boundaries and line numbers |
| `test_hybrid.py` | 3 | Code tokenizer, Reciprocal Rank Fusion, reranker fallback |
| `test_rag.py` | 3 | Chunk indexing, retrieval, prompt and citation requirements |
| `test_graph_builder.py` | 10 | NetworkX graph, PageRank, cycles, orphans, HTML export |
| `test_v2_features.py` | 14 | FTS5, call graph, blast radius, citation verification, MCP |
| `test_cli.py` | 8 | Typer CLI commands and error handling |
| `test_api.py` | 14 | FastAPI endpoints and responses |
| `test_local_repo.py` | 9 | Registering local folders, persistence, isolation |
| `test_folder_picker.py` | 17 | Native folder picker subprocess, cancellation, local-only access |
| `test_github_repo.py` | 12 | GitHub ingestion: URL safety, clone failure/timeout, duplicate URLs, file limits |
| `test_groq.py` | 6 | Groq client, error messages, provider selection, metrics in `/api/ask` |
| `test_public_mode.py` | 6 | Public mode: blocked folder access, per-IP rate limit, model caching |
| `test_embed_backend.py` | 4 | ONNX vs sentence-transformers selection, reranker fallback without PyTorch |

CI (`.github/workflows/ci.yml`) runs the suite on Ubuntu and Windows with Python 3.11 and 3.12.

---

## 3. Retrieval benchmark

### 3.1 Method
- **Dataset:** [`eval/gold.json`](../eval/gold.json), 20 hand-written natural-language questions about **RepoMind's own code**, each labelled with the file(s) that answer it.
- **Corpus:** the RepoMind repository (64 Python files, 500 chunks).
- **Metrics** (k = 5): **Hit@k**, the share of questions where an expected file is in the top k; and **MRR@k**, the mean of 1/rank of the first correct file (0 if not in the top k).
- **Run it:**
  ```bash
  repomind index . && repomind embed
  python eval/run.py          # writes eval/results.md
  ```

### 3.2 Results (October 2026, ONNX MiniLM embeddings)

| Retrieval setup | Hit@5 | MRR@5 |
|---|---|---|
| Vector only | 0.85 | 0.70 |
| Hybrid (vector + BM25, RRF k=60) | 0.80 | 0.56 |
| Hybrid + cross-encoder rerank | 0.85 | 0.67 |
| **Hybrid + lexical rerank (live demo setup)** | **0.85** | **0.70** (Hit@1 0.60, ~0.2 s/query on a laptop CPU) |

Per-question results are in [`eval/results.md`](../eval/results.md).

### 3.3 Interpretation
- On natural-language questions, **BM25 fusion lowered MRR**: test files repeat the vocabulary of the code they test, and keyword search ranks them highly. Reranking recovered the loss.
- The gold set has **no identifier-style queries** (e.g. `verify_citations`), which is where keyword search should help most. That's the next addition.
- 20 questions on one repo is a **regression check**, not a general benchmark.

### 3.4 Known issue
The web UI's **Evaluation** tab runs this RepoMind-specific gold set against whichever repo is selected, so its scores are only meaningful when "RepoMind (Self)" is selected.

---

## 4. Live-system measurements

Measured on the deployed demo (Render free tier, 512 MB, Groq `openai/gpt-oss-120b`):

| Metric | Result |
|---|---|
| Peak memory (startup + clone + index + answer) | 938 MB with PyTorch → **315 MB** with ONNX Runtime (arena off, batch 8) |
| Warm answer time | 4.7–8.2 s end to end; Groq call 0.8–2.4 s |
| Tokens per answer | ~1.3k–3.1k |
| Citation verification on spot checks | 100% on demo-repo questions after requiring full paths in citations |
