"""
Shared fixtures for unit tests.
"""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Fixture for a mocked async database session."""
    return AsyncMock(spec=AsyncSession)
