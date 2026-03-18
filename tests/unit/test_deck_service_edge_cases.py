"""
Unit tests for edge cases in the deck service.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from mnemo.core.exceptions import DeckNameConflictError
from mnemo.services.deck import create_deck


@pytest.mark.asyncio
async def test_create_deck_case_insensitive_name_conflict(mock_db_session: AsyncMock) -> None:
    """Test that creating a deck with a case-insensitive name conflict raises an error."""
    user_id = "test_user"
    deck_name = "My Deck"
    captured_statement = None

    async def side_effect(statement):
        nonlocal captured_statement
        captured_statement = statement
        return MagicMock(scalar_one_or_none=lambda: "existing_deck_id")

    mock_db_session.execute.side_effect = side_effect

    with pytest.raises(DeckNameConflictError):
        await create_deck(
            db=mock_db_session,
            user_id=user_id,
            name=deck_name.lower(),
            description="A test deck",
            tags=[],
        )

    mock_db_session.execute.assert_awaited_once()
    query_str = str(captured_statement.compile(compile_kwargs={"literal_binds": True}))
    assert "lower(decks.name)" in query_str.lower()
