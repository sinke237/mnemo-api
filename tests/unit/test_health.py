"""
Tests for GET /v1/health
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

DB = "mnemo.api.v1.routes.health.check_db_connection"
REDIS = "mnemo.api.v1.routes.health.check_redis_connection"


@pytest.mark.asyncio
async def test_health_returns_200_when_all_healthy(client: AsyncClient) -> None:
    """Health endpoint returns 200 with all systems ok."""
    with (
        patch(DB, new_callable=AsyncMock, return_value=True),
        patch(REDIS, new_callable=AsyncMock, return_value=True),
    ):
        response = await client.get("/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["redis"] == "ok"
    assert body["version"] == "1.0.0"


@pytest.mark.asyncio
async def test_health_returns_degraded_when_db_down(client: AsyncClient) -> None:
    """Health endpoint returns degraded status when DB is unreachable."""
    with (
        patch(DB, new_callable=AsyncMock, return_value=False),
        patch(REDIS, new_callable=AsyncMock, return_value=True),
    ):
        response = await client.get("/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["db"] == "unreachable"
    assert body["redis"] == "ok"


@pytest.mark.asyncio
async def test_health_returns_degraded_when_redis_down(client: AsyncClient) -> None:
    """Health endpoint returns degraded status when Redis is unreachable."""
    with (
        patch(DB, new_callable=AsyncMock, return_value=True),
        patch(REDIS, new_callable=AsyncMock, return_value=False),
    ):
        response = await client.get("/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["db"] == "ok"
    assert body["redis"] == "unreachable"


@pytest.mark.asyncio
async def test_health_response_has_request_id_header(client: AsyncClient) -> None:
    """Every response includes X-Request-ID header per NFR-05.2."""
    with (
        patch(DB, new_callable=AsyncMock, return_value=True),
        patch(REDIS, new_callable=AsyncMock, return_value=True),
    ):
        response = await client.get("/v1/health")

    assert "x-request-id" in response.headers
    assert response.headers["x-request-id"].startswith("req_")