"""
Tests for application configuration and settings validation.
"""

import pytest
from pydantic import ValidationError

from mnemo.core.config import Settings


def test_default_settings_load_successfully() -> None:
    """Settings load with defaults when no env vars are set."""
    s = Settings()
    assert s.app_env == "development"
    assert s.jwt_expiry_seconds == 3600
    assert s.csv_max_size_bytes == 5 * 1024 * 1024


def test_invalid_app_env_raises_validation_error() -> None:
    """app_env only accepts development, staging, production."""
    with pytest.raises(ValidationError):
        Settings(app_env="invalid_env")


def test_is_production_property() -> None:
    s = Settings(
        app_env="production",
        api_key_secret="1234567890123456789012345678901234567890",
    )
    assert s.is_production is True
    assert s.is_development() is False


def test_is_development_property() -> None:
    s = Settings(app_env="development")
    assert s.is_development() is True
    assert s.is_production is False


def test_jwt_secret_too_short_raises_error() -> None:
    """JWT secret must be at least 32 chars (not the dev placeholder)."""
    with pytest.raises(ValidationError):
        Settings(jwt_secret_key="tooshort")
