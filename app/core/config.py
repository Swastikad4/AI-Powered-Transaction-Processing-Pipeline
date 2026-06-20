"""
Application configuration using Pydantic Settings.
Loads values from environment variables and .env file.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from pathlib import Path


class Settings(BaseSettings):
    """Central configuration for the transaction processing pipeline."""

    # Database
    DATABASE_URL: str = Field(
        default="postgresql://pipeline_user:pipeline_pass@postgres:5432/transaction_pipeline",
        description="PostgreSQL connection string",
    )
    POSTGRES_USER: str = "pipeline_user"
    POSTGRES_PASSWORD: str = "pipeline_pass"
    POSTGRES_DB: str = "transaction_pipeline"

    # Redis
    REDIS_URL: str = Field(
        default="redis://redis:6379/0",
        description="Redis connection URL",
    )

    # Celery
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/1"
    CELERY_TASK_ALWAYS_EAGER: bool = Field(
        default=False,
        description="Run Celery tasks synchronously in the same process",
    )

    # Gemini AI
    GEMINI_API_KEY: str = Field(
        default="",
        description="Google Gemini API key for AI enrichment",
    )

    # App
    UPLOAD_DIR: str = "uploads"
    LOG_LEVEL: str = "INFO"
    APP_NAME: str = "AI Transaction Pipeline"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # AI Processing
    AI_BATCH_SIZE: int = Field(
        default=10,
        description="Number of transactions to process in a single AI batch",
    )
    AI_MAX_RETRIES: int = 3
    AI_RETRY_DELAY: float = 1.0  # seconds

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }

    @property
    def upload_path(self) -> Path:
        """Return the upload directory as a Path, creating it if needed."""
        path = Path(self.UPLOAD_DIR)
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance — call this everywhere."""
    return Settings()
