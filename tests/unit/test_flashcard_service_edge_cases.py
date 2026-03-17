"""
Unit tests for edge cases in the flashcard service.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.models.deck import Deck
from mnemo.models.flashcard import Flashcard
from mnemo.services.flashcard import delete_card


@pytest.fixture
def mock_db_session():
    """Fixture for a mocked async database session."""
    return AsyncMock(spec=AsyncSession)


@pytest.mark.asyncio
async def test_delete_card_with_zero_card_count(mock_db_session):
    user_id = "test_user"
    card_id = "test_card"
    deck_id = "test_deck"

    # Create a mock card and deck
    card = Flashcard(id=card_id, deck_id=deck_id)
    deck = Deck(id=deck_id, user_id=user_id, card_count=0, version=1)

    # Mock the database to return the card and deck
    mock_db_session.execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: card),
        MagicMock(scalar_one_or_none=lambda: deck),
        AsyncMock(),  # For the delete(CardMemoryState) call
    ]

    await delete_card(mock_db_session, user_id, card_id)

    # Assert that the card_count is still 0
    assert deck.card_count == 0
