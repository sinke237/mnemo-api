"""
Shared fixtures for unit tests.
"""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.models import CardMemoryState


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Fixture for a mocked async database session."""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def new_memory_state() -> CardMemoryState:
    """Returns a new CardMemoryState with default values."""
    return CardMemoryState(
        card_id="crd_123",
        user_id="usr_123",
        ease_factor=2.5,
        repetitions=0,
        interval_days=0,
        streak=0,
    )
