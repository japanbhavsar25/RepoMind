# RepoMind Deployment & Operations

Three ways to run RepoMind: locally for development, as one Docker container, or as the free hosted setup used by the live demo (Vercel + Render).

---

## 1. Local development

Requires Python 3.11+, Node 18+ and git.

```bash
git clone https://github.com/japanbhavsar25/RepoMind.git
cd RepoMind
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"                             # server + ML + test extras
cp .env.example .env                                # then add GROQ_API_KEY (optional)

uvicorn backend.main:app --port 8001 --reload       # API + Swagger at http://127.0.0.1:8001/docs
cd frontend && npm install && npm run dev           # UI at http://localhost:5173 (proxies /api to :8001)
```

LLM options: set `GROQ_API_KEY` (free key at [console.groq.com](https://console.groq.com)), **or** run Ollama locally (`ollama pull phi3`), **or** neither (evidence-only answers).

If `frontend/dist` exists (after `npm run build`), the API server also serves the built UI at `/`.

---

## 2. Configuration

Settings are read from environment variables or `.env` (names are case-insensitive). See [`backend/config.py`](../backend/config.py).

| Variable | Default | Purpose |
|---|---|---|
| `GROQ_API_KEY` | (empty) | Enables Groq generation. Keep it secret. |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Groq model id |
| `LLM_PROVIDER` | `auto` | `auto` (Groq if a key is set, else Ollama), `groq`, or `ollama` |
| `OLLAMA_URL` / `DEFAULT_OLLAMA_MODEL` | `http://localhost:11434` / `phi3` | Local LLM |
| `PUBLIC_MODE` | `false` | Public server: disables local-folder repos, rate-limits clones |
| `GITHUB_ADDS_PER_HOUR` | `5` | Per-IP clone limit in public mode |
| `MAX_REPO_FILES` / `MAX_FILE_SIZE_BYTES` | `2000` / `2097152` | Ingestion limits |
| `GIT_CLONE_TIMEOUT_SECONDS` | `60` | Clone timeout |
| `EMBED_ON_INDEX` | `true` | Build vector embeddings while indexing |
| `WARMUP_MODELS` | `true` | Load models at startup so the first question is fast |
| `DEFAULT_REPO_ID` | `ecommerce_sample` | Repo selected when the app starts |
| `DATA_DIR` | `.repomind_data/` | Where indexes and clones are stored |
| `REPOMIND_EMBED_BACKEND` | `auto` | `onnx` or `sentence-transformers` (auto picks sentence-transformers if installed) |
| `VITE_API_URL` (frontend build) | (empty, same origin) | Backend URL when the UI is hosted separately; set in `frontend/.env.production` |

---

## 3. Docker (single container)

The [`Dockerfile`](../Dockerfile) builds the React UI, installs the API **without PyTorch** (ONNX embeddings), bakes in the embedding model, and pre-indexes three demo repos. It listens on `$PORT` (default 7860).

```bash
docker build -t repomind .
docker run -p 7860:7860 -e GROQ_API_KEY=gsk_... repomind
# open http://localhost:7860
```

The image sets `PUBLIC_MODE=true` by default.

---

## 4. Free hosting: Render (API) + Vercel (UI)

This is how the live demo runs.

**Backend on Render (free web service, 512 MB):**
1. In Render, choose **New → Blueprint** and select this repo. [`render.yaml`](../render.yaml) defines a free Docker service with health check `/api/health` and `autoDeployTrigger: commit`, so pushes to `main` redeploy.
2. Enter `GROQ_API_KEY` when prompted (stored as a secret).
3. Note the service URL, e.g. `https://repomind-api-xxxx.onrender.com`.

**Frontend on Vercel (Hobby):**
1. Put the backend URL in [`frontend/.env.production`](../frontend/.env.production) as `VITE_API_URL=...` and commit it. It's a public URL, not a secret.
2. In Vercel, choose **Add New → Project**, import the repo, set **Root Directory = `frontend`** (Vite is detected), and deploy.

**Free-tier behaviour to expect:**
- Render sleeps after 15 idle minutes; waking takes about a minute (the UI shows a "waking up" message and retries).
- The disk is ephemeral: repos added by visitors disappear on restart. The demo repos are built into the image.
- Indexing a new repo is slow on 0.1 vCPU (minutes for ~100 chunks).
- Measured peak memory is about 315 MB, which fits in 512 MB.

---

## 5. Operations

- **Health:** `GET /api/health` returns status, version, FTS5 support and whether local repos are enabled.
- **Per-answer metrics:** `POST /api/ask` responses include `model_used`, `latency_ms`, `prompt_tokens` and `completion_tokens`.
- **Re-index:** `POST /api/repos/index?repo_id=...` (or the "Index Repo" button).
