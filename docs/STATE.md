# RepoMind — Project State & Engineering Status (Authoritative)

**Last Updated:** 2026-10-23T06:00:00+05:30  
**Current Phase:** All Core Phases (0 through 9) + Custom Repository Registration + Native Windows Folder Picker (Standalone Topmost Subprocess) **COMPLETED**  
**Overall Status:** GREEN (99/99 tests passing, Ruff clean, Vite build passing, full documentation suite complete)  
**Git Branch:** `master`  
**Network Architecture:** Backend port **8001** (`127.0.0.1:8001`), Frontend port **5173** (Vite proxy `/api` -> `http://127.0.0.1:8001`). Note: port 8000 is reserved for DataPulse.

---

## 1. Feature Status Summary

| Feature / Phase | Description | Status | Verification Status |
|---|---|---|---|
| **Phase 0** | Baseline Audit & Project State Tracking | **COMPLETED** | `docs/INITIAL_AUDIT.md` & `docs/STATE.md` created; 59 baseline tests passing |
| **Phase 1** | Stable Foundation (Backend API, Config, Sample Repo, Health Check, Frontend Scaffold) | **COMPLETED** | FastAPI lifespan, CORS, health endpoint, base schemas |
| **Phase 2** | Structural Analysis & Repository Management (File/Symbol Browser, Frontend Explorer) | **COMPLETED** | AST visitors, symbol table with complexity & call graphs, `FilesView.tsx`, `SymbolsView.tsx` |
| **Phase 3** | Keyword Search (SQLite FTS5, path/type filters, snippet highlighting) | **COMPLETED** | Persistent FTS5 virtual table, code-aware tokenizer, `SearchView.tsx` |
| **Phase 4** | Semantic & Hybrid Search (Embeddings, Weighted RRF, Benchmarking) | **COMPLETED** | ChromaDB lazy embeddings, RRF ($k=60$), query intent classifier |
| **Phase 5** | Grounded Q&A with Citation Verification & Abstention | **COMPLETED** | Regex `[file:start-end]` verification against SQLite, groundedness confidence score, `AskView.tsx` |
| **Phase 6** | Dependency Graph & Change-Impact Analyzer (Downstream blast radius) | **COMPLETED** | NetworkX directed graph, PageRank, cycles, orphans, reverse BFS blast radius, `GraphView.tsx`, `ImpactView.tsx` |
| **Phase 7** | Quantitative Retrieval Evaluation Dashboard | **COMPLETED** | 12 ground truth queries, Hit@1 100%, Hit@5 100%, MRR@5 1.0000, `EvaluationView.tsx` |
| **Phase 8** | Hardening, Security Controls & Deployment Configuration | **COMPLETED** | `resolve_safe_path` traversal protection, SSRF Git URL validation, multi-stage Dockerfile |
| **Phase 9** | Documentation Suite, Code Map & Technical Interview Defense Guide | **COMPLETED** | `ARCHITECTURE_AND_DECISIONS.md`, `TESTING_AND_EVALUATION.md`, `SECURITY_AND_LIMITATIONS.md`, `DEPLOYMENT.md`, `LEARNING_GUIDE.md` |
| **Feature 10** | Custom Local Repository Registration & Isolated Storage | **COMPLETED** | `POST /api/repos/local`, `custom_repos.json` persistence, isolated `.repomind_data/repos/<id>`, `AddRepoModal.tsx` |
| **Feature 11** | **Native Windows Folder Picker Dialog (Topmost Subprocess)** | **COMPLETED** | `POST /api/repos/browse`, standalone Python Tkinter subprocess with `WS_EX_TOPMOST` and foreground focus, PowerShell fallback with topmost owner, guaranteed timeout kill cleanup, loopback & CORS checks, 17 automated tests passing |

---

## 2. Verified Deliverables & Artifacts

1. **Subprocess Native Windows Folder Picker ([`backend/services/folder_picker.py`](file:///d:/RepoMind/backend/services/folder_picker.py)):**
   - **Topmost Foreground Focus Resolution:** Instead of running inside FastAPI's worker threads (which hangs) or opening behind Chrome, the primary picker executes in an isolated Python subprocess with `overrideredirect(True)`, `geometry('0x0+0+0')`, and `attributes('-topmost', True)`. Win32 inspection confirms `WS_EX_TOPMOST = True` on the native dialog (`Select Repository Folder`), ensuring it opens directly in front of the browser.
   - **PowerShell Fallback:** PowerShell fallback updated to remove `-NonInteractive` and initialize a realized, topmost, off-screen owner form to ensure visibility if invoked.
   - **Subprocess Timeout & Guaranteed Cleanup:** Wrapped with `asyncio.wait_for(timeout=120s)`; on timeout or error, explicitly terminates and awaits child processes (`proc.kill()` and `await proc.wait()`) preventing orphaned background processes.
   - **Endpoint ([`backend/routers/repos.py`](file:///d:/RepoMind/backend/routers/repos.py)):** `POST /api/repos/browse` invokes `pick_folder_native()`.
   - **Local-Only & Origin Protection:** Rejects any non-local client IPs (only `127.0.0.1`, `localhost`, `::1` permitted) and validates `Origin` headers against allowed local origins.
   - **Graceful Cancellation Handling:** If the user closes or cancels the dialog, returns `status="cancelled", path=null, cancelled=true` without displaying an error or clearing existing input.
   - **Frontend UI ([`frontend/src/components/AddRepoModal.tsx`](file:///d:/RepoMind/frontend/src/components/AddRepoModal.tsx)):** "Browse Folder" button beside the Local Folder Path field with `FolderOpen` icon, active spinner state, `finally` cleanup, AbortController client timeout, and folder basename auto-fill.
   - **Automated Mock Tests ([`tests/test_folder_picker.py`](file:///d:/RepoMind/tests/test_folder_picker.py)):** 17 automated tests covering selection, cancellation, exception handling, null-byte rejection, remote client rejection, cross-origin checks, script generation, Python and PowerShell subprocess runners, and timeout kill cleanup without opening UI windows during test runs.

2. **Custom Local Repository Registration & Isolated Storage:**
   - Schema validation, isolated `.repomind_data/repos/<id>` databases, and `custom_repos.json` persistence across server restarts.

3. **Core Engine v2.0 & Backend API:**
   - Decoupled FastAPI server on port **8001**.
   - 82 engine, parsing, and integration tests + 17 folder picker tests = **99 total tests**.

4. **React 19 + TypeScript + Tailwind CSS v4 Frontend:**
   - Vite proxy targeting `http://127.0.0.1:8001`.
   - Production bundle verified: `npm run build` completed in 2.05s with zero errors.

---

## 3. Verified Verification Metrics

| Verification Check | Target | Actual Verified Result | Status |
|---|---|---|---|
| Automated Test Suite | `pytest tests/ -v` | **99 passed in 31.27s** (0 failures) | PASS |
| Code Hygiene & Linting | `ruff check repomind backend tests` | **0 errors, 0 warnings** | PASS |
| TypeScript & Production Bundle | `cd frontend; npm run build` | **Built in 2.05s, 0 errors** | PASS |
| Folder Picker Endpoint | `POST /api/repos/browse` | **200 OK (selected, cancelled, error)** | PASS |
| Folder Picker Topmost Window | Win32 `WS_EX_TOPMOST` | **Verified True (foreground dialog)** | PASS |
| UI Redesign | Editorial light theme, teal accent, design tokens, compact density | **Implemented (build + lint passing)** | PASS |
| Folder Picker Remote Guard | Non-local IP client | **403 Forbidden** | PASS |
| Folder Picker Cross-Origin Guard | Malicious `Origin` header | **403 Forbidden** | PASS |
| Subprocess Cleanup | Cancel / Timeout | **Subprocess killed and reaped** | PASS |
| Local Execution | 100% Offline | **Zero cloud API calls, zero telemetry** | PASS |
