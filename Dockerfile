# RepoMind web app: one container serving the FastAPI API and the built React UI.
# Built for Hugging Face Spaces (Docker SDK, port 7860, non-root user 1000),
# but runs anywhere:  docker build -t repomind . && docker run -p 7860:7860 -e GROQ_API_KEY=... repomind

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
    HF_HOME=/home/user/.cache/huggingface \
    PYTHONUNBUFFERED=1

WORKDIR /app

# CPU-only PyTorch keeps the image ~2GB smaller than the default CUDA build
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
COPY pyproject.toml README.md ./
COPY repomind/ repomind/
RUN pip install --no-cache-dir ".[server]"

COPY backend/ backend/
COPY samples/ samples/
COPY --from=frontend /frontend/dist frontend/dist
RUN chown -R user:user /app

USER user

# Bake the search models into the image so startup never downloads them
RUN python -c "from sentence_transformers import SentenceTransformer, CrossEncoder; \
SentenceTransformer('all-MiniLM-L6-v2'); CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

# Pre-index the bundled sample and one real GitHub repo so the demo is instant
RUN python -c "from backend.services.repo_manager import repo_manager as m; \
m.index_repo('ecommerce_sample'); \
r, _ = m.add_github_repo('https://github.com/pallets/itsdangerous'); \
m.index_repo(r.id)"

ENV HF_HUB_OFFLINE=1 \
    PUBLIC_MODE=true \
    DEFAULT_REPO_ID=gh_pallets_itsdangerous_0eed211a

EXPOSE 7860
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860"]
