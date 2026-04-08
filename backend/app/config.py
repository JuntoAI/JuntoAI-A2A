"""Application configuration via environment variables."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings loaded from environment variables with sensible defaults."""

    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000"
    GOOGLE_CLOUD_PROJECT: str = ""

    # --- Local Battle Arena fields ---
    RUN_MODE: Literal["cloud", "local"] = "local"
    SQLITE_DB_PATH: str = "data/juntoai.db"
    LLM_PROVIDER: str = "ollama"
    LLM_MODEL_OVERRIDE: str = ""
    MODEL_MAP: str = ""
    OLLAMA_BASE_URL: str = "http://ollama:11434"
    OLLAMA_MODEL: str = "llama3.1"

    # --- Cloud-only: Share image storage ---
    GCS_BUCKET_NAME: str = ""
    VERTEX_AI_LOCATION: str = "europe-west1"

    # --- Cloud-only: Admin dashboard ---
    ADMIN_PASSWORD: str = ""

    # --- Cloud-only: Amazon SES (email verification) ---
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_SES_REGION: str = "us-east-1"
    SES_SENDER_EMAIL: str = "noreply@juntoai.org"
    FRONTEND_URL: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        return [o.strip() for o in self.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
