"""
Application settings loaded from environment variables.
Uses pydantic-settings for validation and type coercion.
"""

from functools import lru_cache

from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────────────────
    app_env: str = Field(default="development", pattern="^(development|staging|production)$")
    app_debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    api_base_url: str = Field(default="http://localhost:8000")

    # ── Database ───────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://mnemo:changeme_in_production@localhost:5432/mnemo"
    )

    # ── Redis ──────────────────────────────────────────────────────────────────
    redis_url: str = Field(default="redis://localhost:6379/0")

    # ── Auth ───────────────────────────────────────────────────────────────────
    jwt_secret_key: str = Field(default="dev_secret_replace_in_production_with_64_char_hex")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expiry_seconds: int = Field(default=3600)
    api_key_live_prefix: str = Field(default="mnm_live_")
    api_key_test_prefix: str = Field(default="mnm_test_")
    # Secret used specifically for API key HMAC hashing. Separate from JWT secret
    # so rotating JWT signing keys does not invalidate stored API keys.
    api_key_secret: str = Field(default="dev_apikey_secret_replace_in_production_with_64_char_hex")

    # ── Rate Limiting ──────────────────────────────────────────────────────────
    rate_limit_read_per_minute: int = Field(default=600)
    rate_limit_write_per_minute: int = Field(default=120)
    rate_limit_answer_per_minute: int = Field(default=60)
    rate_limit_import_per_hour: int = Field(default=10)
    rate_limit_auth_per_minute: int = Field(default=30)

    # Maximum request body size (bytes) for general JSON/form payloads.
    # Large file uploads (CSV) are handled by specific endpoints.
    max_request_body_bytes: int = Field(default=1 * 1024 * 1024)

    # ── Import ─────────────────────────────────────────────────────────────────
    csv_max_size_bytes: int = Field(default=5 * 1024 * 1024)  # 5 MB

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        if v == "dev_secret_replace_in_production_with_64_char_hex":
            return v  # allow in dev
        if len(v) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters")
        return v

    @field_validator("api_key_secret")
    @classmethod
    def validate_api_key_secret(cls, v: str, info: ValidationInfo) -> str:
        if v == "dev_apikey_secret_replace_in_production_with_64_char_hex":
            if info.data.get("app_env", "development") != "development":
                raise ValueError(
                    "API_KEY_SECRET must be set to a secure value in non-development environments"
                )
            return v  # allow in dev
        if len(v) < 32:
            raise ValueError("API_KEY_SECRET must be at least 32 characters")
        return v

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    """
    Returns cached settings instance.
    Use this as a FastAPI dependency: Depends(get_settings)
    """
    return Settings()
