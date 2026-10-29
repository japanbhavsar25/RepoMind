"""Application configuration and environment settings."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """RepoMind global configuration."""
    project_name: str = "RepoMind"
    version: str = "2.0.0"
    api_prefix: str = "/api"

    # Server host & port (default to 8001; 8000 is reserved for DataPulse)
    host: str = "127.0.0.1"
    port: int = 8001

    # Directory layout
    base_dir: Path = Path(__file__).resolve().parent.parent
    data_dir: Path = base_dir / ".repomind_data"
    samples_dir: Path = base_dir / "samples"
    
    # Active default repo
    default_repo_id: str = "ecommerce_sample"

    # LLM configuration
    # "auto" uses Groq when GROQ_API_KEY is set, otherwise local Ollama.
    llm_provider: str = "auto"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    ollama_url: str = "http://localhost:11434"
    default_ollama_model: str = "phi3"

    # Build the ChromaDB vector index as part of indexing (needed for semantic Q&A)
    embed_on_index: bool = True
    # Load the embedding + reranker models at startup so the first question is fast
    warmup_models: bool = True

    # Public deployment mode (e.g. Hugging Face Spaces): disables registering
    # server-side folders and rate-limits GitHub cloning per client IP and overall.
    public_mode: bool = False
    github_adds_per_hour: int = 5
    github_adds_per_hour_total: int = 20

    # Security limits
    max_file_size_bytes: int = 2 * 1024 * 1024  # 2MB max per single file
    max_repo_files: int = 2000
    git_clone_timeout_seconds: int = 60

    # CORS: explicit origins only. A "*" here would let any website a developer
    # visits read files from their local server. Override with CORS_ORIGINS='[...]'.
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8001",
        "http://127.0.0.1:8001",
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://repo-mind-steel.vercel.app",
    ]

    # Also read .env, and ignore variables in it that aren't settings here
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
# Ensure runtime data directories exist
settings.data_dir.mkdir(parents=True, exist_ok=True)
