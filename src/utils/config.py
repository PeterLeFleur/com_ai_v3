# src/utils/config.py
from __future__ import annotations

import json
from typing import Optional, List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central app settings loaded from environment (.env).
    Extra env vars are ignored to avoid crashes during transitions.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",            # accept unknown env vars gracefully
        case_sensitive=False,
    )

    # --- OpenAI ---
    openai_api_key: Optional[str] = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_model: Optional[str] = Field(default="gpt-4o", validation_alias="OPENAI_MODEL")

    # --- Anthropic ---
    anthropic_api_key: Optional[str] = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    anthropic_model: Optional[str] = Field(default="claude-3-5-sonnet-20241022", validation_alias="ANTHROPIC_MODEL")

    # --- Google Gemini ---
    gemini_api_key: Optional[str] = Field(default=None, validation_alias="GEMINI_API_KEY")
    gemini_model: Optional[str] = Field(default="gemini-1.5-pro", validation_alias="GEMINI_MODEL")

    # --- Firebase (client) ---
    firebase_api_key: Optional[str] = Field(default=None, validation_alias="FIREBASE_API_KEY")
    firebase_auth_domain: Optional[str] = Field(default=None, validation_alias="FIREBASE_AUTH_DOMAIN")
    firebase_project_id: Optional[str] = Field(default=None, validation_alias="FIREBASE_PROJECT_ID")
    firebase_storage_bucket: Optional[str] = Field(default=None, validation_alias="FIREBASE_STORAGE_BUCKET")
    firebase_messaging_sender_id: Optional[str] = Field(default=None, validation_alias="FIREBASE_MESSAGING_SENDER_ID")
    firebase_app_id: Optional[str] = Field(default=None, validation_alias="FIREBASE_APP_ID")
    firebase_measurement_id: Optional[str] = Field(default=None, validation_alias="FIREBASE_MEASUREMENT_ID")

    # --- Firebase Admin / GCP ---
    google_application_credentials: Optional[str] = Field(default=None, validation_alias="GOOGLE_APPLICATION_CREDENTIALS")

    # --- PostgreSQL ---
    postgres_host: Optional[str] = Field(default="localhost", validation_alias="POSTGRES_HOST")
    postgres_port: Optional[int] = Field(default=5432, validation_alias="POSTGRES_PORT")
    postgres_db: Optional[str] = Field(default=None, validation_alias="POSTGRES_DB")
    postgres_user: Optional[str] = Field(default=None, validation_alias="POSTGRES_USER")
    postgres_password: Optional[str] = Field(default=None, validation_alias="POSTGRES_PASSWORD")
    database_url: Optional[str] = Field(default=None, validation_alias="DATABASE_URL")

    # --- App settings ---
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    # Treat CORS_ORIGINS as a simple string; expose a parsed list via property below
    cors_origins: Optional[str] = Field(default=None, validation_alias="CORS_ORIGINS")

    # --- Provider settings ---
    provider_timeout: int = Field(default=30, validation_alias="PROVIDER_TIMEOUT")
    provider_max_retries: int = Field(default=3, validation_alias="PROVIDER_MAX_RETRIES")
    provider_cache_ttl: int = Field(default=300, validation_alias="PROVIDER_CACHE_TTL")

    # --- Feature flags ---
    firestore_mirror_enabled: bool = Field(default=False, validation_alias="FIRESTORE_MIRROR_ENABLED")

    # ---------- Helpers ----------
    @property
    def cors_origins_list(self) -> List[str]:
        """
        Accept either:
        - comma-separated: "http://a,http://b"
        - JSON array string: '["http://a","http://b"]'
        """
        if not self.cors_origins:
            return ["http://localhost:3000", "http://localhost:8000"]
        s = self.cors_origins.strip()
        if s.startswith("["):
            try:
                arr = json.loads(s)
                if isinstance(arr, list):
                    return [str(x).strip() for x in arr if str(x).strip()]
            except Exception:
                pass
        return [part.strip() for part in s.split(",") if part.strip()]


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
