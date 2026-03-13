"""
Pytest plugin to override database URL for tests to use SQLite in-memory DB.
"""

import os

import pytest


@pytest.fixture(autouse=True, scope="session")
def set_sqlite_database_url():
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
    yield
    os.environ.pop("DATABASE_URL", None)
