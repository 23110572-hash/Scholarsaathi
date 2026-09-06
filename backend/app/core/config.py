from functools import lru_cache
from pathlib import Path
from typing import Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = PROJECT_ROOT / ".env"
DEVELOPMENT_SECRET = "local-development-secret-change-before-deploy"


class Settings(BaseSettings):
    app_name: str = "ScholarSaathi API"
    app_env: str = "development"
    database_url: str
    app_secret_key: SecretStr = SecretStr(DEVELOPMENT_SECRET)
    session_cookie_name: str = "scholarsaathi_session"
    session_cookie_secure: bool = False
    session_ttl_hours: int = 24
    application_intent_cookie_name: str = "scholarsaathi_application_intent"
    application_intent_ttl_hours: int = Field(default=72, ge=1, le=24 * 30)
    supabase_s3_endpoint: str | None = None
    supabase_s3_region: str | None = None
    supabase_s3_bucket: str | None = None
    supabase_s3_access_key_id: SecretStr | None = None
    supabase_s3_secret_access_key: SecretStr | None = None
    supabase_s3_upload_max_bytes: int = Field(
        default=10 * 1024 * 1024, ge=1024, le=50 * 1024 * 1024
    )
    supabase_s3_signed_url_ttl_seconds: int = Field(default=300, ge=60, le=3600)
    cors_origins: str = "https://scholarsaathi-two.vercel.app"
    openrouter_api_key: SecretStr | None = None
    ai_model: str = "openai/gpt-4o-mini"
    ai_timeout_seconds: float = Field(default=45.0, gt=0, le=120)
    ai_max_retries: int = Field(default=2, ge=0, le=5)
    # Discovery prompt token limit budget.
    ai_token_budget: int = Field(default=16000, ge=2000, le=1_000_000)
    # Candidates sent to the model per discovery request.
    ai_discovery_max_candidates: int = Field(default=4, ge=1, le=12)
    # Per-chunk evidence truncation.
    ai_discovery_evidence_char_limit: int = Field(default=900, ge=200, le=20_000)

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("DATABASE_URL is required")
        url = value.strip()
        if url.startswith("postgresql+psycopg://"):
            return url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+psycopg://", 1)
        raise ValueError("DATABASE_URL must be a PostgreSQL connection string")

    @model_validator(mode="after")
    def validate_production_security(self) -> Self:
        storage_values = (
            self.supabase_s3_endpoint,
            self.supabase_s3_region,
            self.supabase_s3_bucket,
            (
                self.supabase_s3_access_key_id.get_secret_value()
                if self.supabase_s3_access_key_id
                else None
            ),
            (
                self.supabase_s3_secret_access_key.get_secret_value()
                if self.supabase_s3_secret_access_key
                else None
            ),
        )
        configured = [bool(value and value.strip()) for value in storage_values]
        if any(configured) and not all(configured):
            raise ValueError("All SUPABASE_S3 connection settings must be provided together")

        if self.app_env.strip().lower() != "production":
            return self

        secret = self.app_secret_key.get_secret_value()
        if secret == DEVELOPMENT_SECRET or len(secret) < 32:
            raise ValueError("APP_SECRET_KEY must contain at least 32 characters in production")
        if not self.session_cookie_secure:
            raise ValueError("SESSION_COOKIE_SECURE must be true in production")
        if not self.allowed_origins or any(
            not origin.startswith("https://") for origin in self.allowed_origins
        ):
            raise ValueError("CORS_ORIGINS must contain HTTPS origins in production")
        return self

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
