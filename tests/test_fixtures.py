from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.api.dependencies import current_user_dep
from mnemo.core.constants import PermissionScope
from mnemo.db.database import Base, engine, get_db
from mnemo.main import app
from mnemo.models import User


@pytest.fixture(scope="function", autouse=True)
async def create_test_database():
    """Drop and recreate all tables before each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


@pytest.fixture
async def db(create_test_database) -> AsyncGenerator[AsyncSession, None]:
    """
    Establishes a single transaction for the duration of a test.

    A new session is created for each request, but all sessions share the same
    underlying database connection and transaction. This allows the test to
    make assertions about the state of the database across multiple API calls,
    while ensuring that each request has its own isolated session to prevent
    concurrent access errors.

    At the end of the test, the transaction is rolled back, leaving the database
    in a clean state.
    """
    connection = await engine.connect()
    transaction = await connection.begin()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        """Dependency override for get_db that provides a session within the test's transaction."""
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()

    app.dependency_overrides[get_db] = override_get_db

    # Provide a session for the test function itself, using the same connection.
    test_session = AsyncSession(bind=connection, expire_on_commit=False)
    yield test_session
    await test_session.close()

    await transaction.rollback()
    await connection.close()
    del app.dependency_overrides[get_db]


@pytest.fixture
def authenticated_user() -> User:
    """Return a valid user object, as would be returned by get_current_user_from_token."""
    user = User(
        id="usr_b2c3d4e5f6a7b8a1",
        country="US",
        timezone="America/New_York",
        display_name="Test User",
    )
    user.token_scopes = [scope.value for scope in PermissionScope]
    return user


@pytest.fixture
async def client(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch, authenticated_user: User
) -> AsyncClient:
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

    app.dependency_overrides[current_user_dep] = lambda: authenticated_user

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    del app.dependency_overrides[current_user_dep]
