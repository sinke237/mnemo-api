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
