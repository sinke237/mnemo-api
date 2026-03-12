"""
Tests for main app and middleware.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from mnemo.core.config import get_settings
from mnemo.main import app


@pytest.mark.asyncio
async def test_root_endpoint() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Mnemo Learning API v1. See /docs for the API reference."}


@pytest.mark.asyncio
async def test_request_id_middleware() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/")
    assert "X-Request-ID" in response.headers
    assert response.headers["X-Request-ID"].startswith("req_")


@pytest.mark.asyncio
async def test_https_enforcement_middleware_production() -> None:
    settings = get_settings()
    original_app_env = settings.app_env
    settings.app_env = "production"

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "HTTP_NOT_ALLOWED"
    finally:
        settings.app_env = original_app_env
