from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from mnemo.db.database import Base, engine
from mnemo.main import app


# Create all tables before each test (for in-memory SQLite)
@pytest.fixture(scope="function", autouse=True)
async def create_test_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


@pytest.fixture
async def client(monkeypatch: pytest.MonkeyPatch) -> AsyncClient:
    """
    Async HTTP client pointed at the FastAPI app.
    Does NOT require a running server — uses ASGI transport directly.
    Mocks Redis for the duration of the test.
    """
    mock_redis_client = AsyncMock()
    mock_redis_client.ping.return_value = True
    mock_redis_client.rpush.return_value = 1
    mock_redis_client.blpop.return_value = None  # No job in queue by default

    monkeypatch.setattr("mnemo.db.redis.get_redis", lambda: mock_redis_client)
    monkeypatch.setattr("mnemo.services.import_job.get_redis", lambda: mock_redis_client)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
