"""
Shared pytest fixtures for all tests.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from mnemo.main import app


@pytest.fixture
async def client() -> AsyncClient:
    """
    Async HTTP client pointed at the FastAPI app.
    Does NOT require a running server — uses ASGI transport directly.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
