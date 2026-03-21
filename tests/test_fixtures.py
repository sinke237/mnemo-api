import logging
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.api.dependencies import get_current_user_from_token
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
    connection = await engine.connect()
    transaction = await connection.begin()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()

    app.dependency_overrides[get_db] = override_get_db

    test_session = AsyncSession(bind=connection, expire_on_commit=False)
    yield test_session
    await test_session.close()

    await transaction.rollback()
    await connection.close()
    del app.dependency_overrides[get_db]


@pytest.fixture
def authenticated_user() -> User:
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
    mock_redis_client = AsyncMock()
    mock_redis_client.ping.return_value = True
    mock_redis_client.rpush.return_value = 1
    mock_redis_client.blpop.return_value = None

    monkeypatch.setattr("mnemo.db.redis.get_redis", lambda: mock_redis_client)
    monkeypatch.setattr("mnemo.services.import_job.get_redis", lambda: mock_redis_client)

    app.dependency_overrides[get_current_user_from_token] = lambda: authenticated_user

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    del app.dependency_overrides[get_current_user_from_token]


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a per-test AsyncSession using AsyncSessionLocal with a
    transaction started and rolled back afterwards to isolate test data.
    """
    # Use a top-level DB connection + outer transaction, then create a
    # nested transaction (SAVEPOINT) for the test. This allows tests to
    # call `await db_session.commit()` without making permanent changes
    # (the outer transaction will be rolled back at teardown).
    connection = await engine.connect()
    outer_transaction = await connection.begin()

    session = AsyncSession(bind=connection, expire_on_commit=False)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        try:
            yield session
        finally:
            await session.close()

    app.dependency_overrides[get_db] = override_get_db

    # Begin a SAVEPOINT so commits inside the test are contained.
    await session.begin_nested()

    try:
        yield session
    finally:
        # Rollback nested transaction (savepoint) and close session,
        # then rollback the outer transaction and close connection.
        try:
            await session.rollback()
        except Exception:
            logging.exception("Error rolling back test session nested transaction")
        await session.close()
        await outer_transaction.rollback()
        await connection.close()
        del app.dependency_overrides[get_db]
