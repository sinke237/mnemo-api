"""
Database connection management.
Uses SQLAlchemy async engine with asyncpg driver.
"""

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool

from mnemo.core.config import get_settings

settings = get_settings()


if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    if ":memory:" in settings.database_url:
        # Use StaticPool for in-memory SQLite so tables persist across connections.
        engine = create_async_engine(
            settings.database_url,
            echo=settings.is_development(),
            connect_args=connect_args,
            poolclass=StaticPool,
        )
    else:
        engine = create_async_engine(
            settings.database_url,
            echo=settings.is_development(),
            connect_args=connect_args,
        )
else:
    engine = create_async_engine(
        settings.database_url,
        echo=settings.is_development(),  # log SQL in dev only
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,  # verify connections before use
    )

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    join_transaction_mode="create_savepoint",
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a database session per request.
    Commits on success, rolls back on exception.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_db_connection() -> bool:
    """
    Health check: verify the database is reachable and responsive.
    Returns True if healthy, False otherwise.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
