"""
Database connection management.
Uses SQLAlchemy async engine with asyncpg driver.
"""

from collections.abc import AsyncGenerator
from sqlite3 import Connection as SQLite3Connection

from sqlalchemy import event, text
from sqlalchemy.engine import Connection as SAConnection
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool

from mnemo.core.config import get_settings

settings = get_settings()


url = make_url(settings.database_url)

if url.drivername.startswith("sqlite"):
    url = url.set(drivername="sqlite+aiosqlite")
    engine = create_async_engine(
        url,
        echo=settings.is_development,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool if url.database == ":memory:" else None,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(
        dbapi_connection: SQLite3Connection, connection_record: SAConnection
    ) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

else:
    engine = create_async_engine(
        url,
        echo=settings.is_development,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield a database session for use in tests or scripts.
    Ensures the session is closed after use.
    """
    async with AsyncSessionLocal() as session:
        yield session


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
