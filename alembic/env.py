"""Alembic environment configuration for async SQLAlchemy."""

import asyncio
import sys
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Make sure src/ is on the path so we can import mnemo
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from mnemo.core.config import get_settings
from mnemo.db.database import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

# Import all models here so Alembic can detect them for autogenerate
from mnemo.models import api_key, card_memory_state, deck, flashcard, idempotency_key, user

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    try:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
        await connectable.dispose()
    except Exception as exc:  # pragma: no cover - fallback for missing DB during local dev
        # If the database is unreachable (e.g. running locally without Postgres),
        # detect if the user requested autogenerate. Autogenerate requires an
        # online DB connection (Alembic needs to inspect the current DB schema),
        # so we must fail fast with a helpful message instead of falling back to
        # offline mode (which cannot satisfy autogenerate and leads to confusing
        # errors like "Can't use literal_binds setting without as_sql mode").
        import sys

        if "--autogenerate" in sys.argv:
            print("Error: cannot run `--autogenerate` because the database is unreachable.")
            print(f"Database connection error: {exc}")
            print("Ensure the configured DATABASE_URL points to an accessible Postgres instance, or run alembic inside your docker-compose 'api' container.")
            raise

        # For non-autogenerate operations (e.g., offline `upgrade --sql`), fall
        # back to the offline path so users can generate SQL scripts without a
        # live DB during local development.
        print(
            "Warning: could not connect to the database; running in offline mode instead."
        )
        print(f"Database connection error: {exc}")
        run_migrations_offline()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
