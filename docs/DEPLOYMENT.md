# RepoMind Deployment & Operations Guide

This guide describes how to run RepoMind v2.0 in local development, as a self-hosted single service, or inside containerized Docker environments.

---

## 1. Prerequisites & Environment

- **Operating System:** Windows 10/11, macOS 12+, or modern Linux (Ubuntu 22.04+).
- **Python:** Python 3.10, 3.11, or 3.12 (tested on Python 3.12.1).
- **Node.js:** Node.js 18.x or newer with npm (tested on Node.js 24.15.0 & npm 11.12.1).
- **Hardware:** 8 GB RAM minimum; 2 GB free disk space for ChromaDB embeddings and SQLite indices.
- **Git:** Git 2.30+ installed and available on `PATH`.
- **Optional Local LLM:** [Ollama](https://ollama.com) running locally (`ollama serve`) with any model (e.g., `ollama pull mistral` or `ollama pull qwen2.5-coder:7b`).

---

## 2. Quickstart: Local Development

### Step 1: Clone & Python Virtual Environment Setup

```powershell
# Clone the repository
git clone https://github.com/your-username/RepoMind.git
cd RepoMind

# Create and activate a Python virtual environment
python -m venv .venv

# On Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# On Linux / macOS:
# source .venv/bin/activate

# Install dependencies in editable mode
pip install -e .
pip install -r backend/requirements.txt
```

### Step 2: Start the FastAPI Backend Server

```powershell
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

- Backend API root: `http://127.0.0.1:8000`
- Interactive OpenAPI Swagger Docs: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/api/health`

### Step 3: Start the Vite + React Frontend

In a separate terminal:

```powershell
cd frontend
npm install
npm run dev
```

- Web UI: `http://localhost:5173`
- The frontend connects automatically to the backend at `http://127.0.0.1:8000` (or the configured `VITE_API_BASE_URL`).

---

## 3. Environment Configuration

RepoMind utilizes Pydantic BaseSettings and reads from environment variables or a `.env` file in the project root:

| Variable | Default Value | Description |
|---|---|---|
| `REPOMIND_HOST` | `127.0.0.1` | Backend HTTP bind address. |
| `REPOMIND_PORT` | `8000` | Backend HTTP port. |
| `REPOMIND_DATA_DIR` | `.repomind_data` | Directory for persistent SQLite DBs and Chroma collections. |
| `REPOMIND_CORS_ORIGINS` | `["http://localhost:5173", "http://127.0.0.1:5173"]` | Allowed CORS origins for the frontend SPA. |
| `REPOMIND_OLLAMA_URL` | `http://127.0.0.1:11434` | Endpoint of the local Ollama instance (optional). |
| `REPOMIND_OLLAMA_MODEL` | `mistral` | Default LLM model identifier for Q&A generation. |
| `REPOMIND_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | SentenceTransformer model used for dense code vectors. |

---

## 4. CLI Commands Reference

RepoMind provides a rich CLI interface powered by Typer and Rich:

```powershell
# 1. Parse and index AST symbols, cyclomatic complexity, and call graph into SQLite
repomind index <repository_path>

# 2. Chunk symbols and generate ChromaDB dense vector embeddings
repomind embed <repository_path>

# 3. Query the codebase with grounded citations
repomind ask "Where is password hashing implemented?"

# 4. Compute the downstream blast radius of a file or symbol change
repomind impact models.py
repomind impact OrderService.checkout

# 5. Run the quantitative retrieval evaluation benchmark (Hit@1, Hit@5, MRR@5)
repomind evaluate

# 6. Generate a dependency graph and analyze PageRank, cycles, and orphans
repomind graph <repository_path>

# 7. Generate a Git churn hotspot risk analysis and interactive HTML report
repomind report <repository_path>

# 8. Start the Model Context Protocol (MCP) server for Claude / AI IDE integration
repomind mcp
```

---

## 5. Production Build & Unified Serving

You can compile the frontend into static assets and serve them directly via FastAPI or an Nginx reverse proxy.

### 5.1 Compiling Frontend Assets

```powershell
cd frontend
npm run build
```

This outputs static HTML, CSS, and JS bundles to `frontend/dist/`.

### 5.2 Serving Frontend via FastAPI Static Files

FastAPI can mount `frontend/dist/` directly:

```python
from fastapi.staticfiles import StaticFiles

app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="frontend")
```

Now accessing `http://127.0.0.1:8000` serves the full-stack web application from a single process.

---

## 6. Docker Containerization

### 6.1 Multi-Stage `Dockerfile`

```dockerfile
# Stage 1: Build the React 19 Frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python Backend Runtime
FROM python:3.12-slim
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    REPOMIND_HOST=0.0.0.0 \
    REPOMIND_PORT=8000

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY repomind/ ./repomind/
COPY backend/ ./backend/
COPY samples/ ./samples/
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 6.2 `docker-compose.yml`

```yaml
version: '3.8'

services:
  repomind:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - repomind_data:/app/.repomind_data
    environment:
      - REPOMIND_HOST=0.0.0.0
      - REPOMIND_PORT=8000
      - REPOMIND_OLLAMA_URL=http://host.docker.internal:11434
    restart: unless-stopped

volumes:
  repomind_data:
```
