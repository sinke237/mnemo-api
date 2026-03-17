"""
Unit tests for edge cases in the deck service.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.core.exceptions import DeckNameConflictError
from mnemo.services.deck import create_deck


@pytest.fixture
def mock_db_session():
    """Fixture for a mocked async database session."""
    return AsyncSession()


@pytest.mark.asyncio
async def test_create_deck_case_insensitive_name_conflict(mock_db_session):
    user_id = "test_user"
    deck_name = "My Deck"

    # Mock the database to return a deck with the same name but different case
    mock_db_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=lambda: "existing_deck_id")
    )

    with pytest.raises(DeckNameConflictError):
        await create_deck(
            mock_db_session,
            user_id,
            deck_name.lower(),
            "A test deck",
            [],
        )
