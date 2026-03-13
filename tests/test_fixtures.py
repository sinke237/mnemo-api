import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from mnemo.db.database import Base, engine
from mnemo.main import app


# Create all tables before any tests run (for in-memory SQLite)
@pytest.fixture(scope="session", autouse=True)
def create_test_database():
    async def _create():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.get_event_loop().run_until_complete(_create())


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
