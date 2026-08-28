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
    cors_origins: str = "http://localhost:5173"
    groq_api_key: SecretStr | None = None
    groq_model: str = "openai/gpt-oss-20b"
    groq_timeout_seconds: float = Field(default=45.0, gt=0, le=120)
    groq_max_retries: int = Field(default=2, ge=0, le=5)

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
