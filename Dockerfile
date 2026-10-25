# RepoMind web app: one container serving the FastAPI API (and the built React UI).
# Slim build for 512 MB hosts such as Render's free tier: no PyTorch. Embeddings
# run on ChromaDB's bundled ONNX MiniLM; reranking uses the lexical heuristic.
#   docker build -t repomind . && docker run -p 7860:7860 -e GROQ_API_KEY=... repomind

# ---- Stage 1: build the React frontend ----
FROM node:22-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python backend ----
FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    PYTHONUNBUFFERED=1 \
    REPOMIND_EMBED_BACKEND=onnx

WORKDIR /app

COPY pyproject.toml README.md ./
COPY repomind/ repomind/
RUN pip install --no-cache-dir ".[server]"

COPY backend/ backend/
COPY samples/ samples/
COPY --from=frontend /frontend/dist frontend/dist
RUN chown -R user:user /app

USER user

# Bake the ONNX embedding model into the image so startup never downloads it
RUN python -c "from repomind.embedder import CodeEmbedder; CodeEmbedder().embed_texts(['warm up'])"

# Pre-index the bundled sample, RepoMind's own code and one real GitHub repo so the demo is instant
RUN python -c "from backend.services.repo_manager import repo_manager as m; \
m.index_repo('ecommerce_sample'); \
m.index_repo('repomind_core'); \
r, _ = m.add_github_repo('https://github.com/pallets/itsdangerous'); \
m.index_repo(r.id)"

ENV PUBLIC_MODE=true \
    DEFAULT_REPO_ID=gh_pallets_itsdangerous_0eed211a \
    PORT=7860

EXPOSE 7860
# Hosts like Render inject PORT; default 7860
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"]
