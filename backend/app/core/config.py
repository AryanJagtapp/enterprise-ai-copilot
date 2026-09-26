"""
Application configuration.

Loads settings from environment variables (via a .env file in local/dev,
real environment variables in staging/production). Never hard-code secrets
here — this module only defines *names* and safe defaults.
"""
from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App identity ---
    app_name: str = "Enterprise AI Knowledge & Workflow Copilot"
    environment: str = Field(default="development")  # development | staging | production
    api_prefix: str = "/api/v1"

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000
    cors_allow_origins: List[str] = ["http://localhost:5173"]

    # --- LLM (Gemini only — no OpenAI) ---
    gemini_api_key: str = Field(default="", description="Set via GEMINI_API_KEY env var")
    gemini_model: str = "gemini-2.0-flash"

    # --- Hugging Face models ---
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    hf_models_enabled: bool = True
    # Staging (Render free tier, 512MB RAM) can't hold both the embedding
    # model and the cross-encoder reranker in memory at once without OOM-ing.
    # This flag lets the reranker be switched off via one env var
    # (RERANKER_ENABLED=false) without touching hybrid retrieval (BM25 +
    # dense embeddings), which stays fully intact either way. Defaults to
    # True so local dev and any higher-memory environment keep reranking on.
    reranker_enabled: bool = True

    # --- Storage ---
    database_url: str = "sqlite:///./data/app.db"
    vector_store_path: str = "./data/vector_store"
    upload_dir: str = "./data/uploads"
    max_upload_mb: int = 25
    allowed_upload_extensions: List[str] = [".pdf", ".docx", ".txt"]

    # --- Security gateway ---
    max_agent_steps: int = 6
    tool_timeout_seconds: int = 15
    enable_pii_redaction: bool = True

    # --- Observability ---
    log_level: str = "INFO"
    log_json: bool = True

    # --- Retry / resilience ---
    llm_max_retries: int = 2
    llm_retry_backoff_seconds: float = 1.5


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton — read once per process."""
    return Settings()
