FROM python:3.11-slim
WORKDIR /work
COPY pyproject.toml README.md ./
COPY repomind/ repomind/
RUN pip install --no-cache-dir -e .
# Ollama runs separately: docker run -d -p 11434:11434 ollama/ollama
# App usage: docker run --rm -v .:/work repomind index /work --db /tmp/r.db
CMD ["repomind", "--help"]
