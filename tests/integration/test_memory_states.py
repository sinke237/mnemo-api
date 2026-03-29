"""
Integration tests for memory state services and endpoints.
Covers due card logic with timezones, weak spots, and sorting.
"""

from datetime import datetime, timedelta

import pytest
import pytz
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.models import CardMemoryState, Deck, Flashcard, User
from mnemo.services.spaced_repetition import get_due_cards, get_weak_spots

# Register shared fixtures
pytest_plugins = ["tests.test_fixtures"]

# Mark all tests in this module as async
pytestmark = pytest.mark.asyncio


@pytest.fixture
async def user_with_timezone(db: AsyncSession) -> User:
    """Fixture for a user with a specific timezone."""
    user = User(
        id="usr_timezone_test",
        email="tz-test@example.com",
        normalized_email="tz-test@example.com",
        country="CM",  # Cameroon
        timezone="Africa/Douala",  # UTC+1
        display_name="Timezone Tester",
    )
    db.add(user)
    await db.commit()
    return user


@pytest.fixture
async def deck_for_memory_states(db: AsyncSession, user_with_timezone: User) -> Deck:
    """Fixture for a deck to hold cards for memory state tests."""
    deck = Deck(
        id="dck_mem_test",
        name="Memory State Test Deck",
        user_id=user_with_timezone.id,
    )
    db.add(deck)
    await db.commit()
    return deck


async def test_get_due_cards_respects_user_timezone(
    db: AsyncSession, user_with_timezone: User, deck_for_memory_states: Deck
):
    """
    Test that get_due_cards correctly identifies cards due "today" in the user's
    local timezone, even if it's still "yesterday" in UTC.
    """
    user_tz = pytz.timezone(user_with_timezone.timezone)

    # This is 00:30 AM in user's local time (UTC+1)
    # But 23:30 PM the previous day in UTC.
    due_time_local = datetime.now(user_tz).replace(hour=0, minute=30, second=0)
    due_time_utc = due_time_local.astimezone(pytz.utc)

    card = Flashcard(
        id="crd_tz_test",
        deck_id=deck_for_memory_states.id,
        question="Timezone test",
        answer="Works",
    )
    db.add(card)
    await db.flush()

    memory_state = CardMemoryState(
        card_id=card.id,
        user_id=user_with_timezone.id,
        due_at=due_time_utc,
    )
    db.add(memory_state)
    await db.commit()

    due_cards_result = await get_due_cards(db, user_with_timezone)
    due_cards = [item[0] for item in due_cards_result]  # Unpack tuple

    assert len(due_cards) == 1
    assert due_cards[0].card_id == "crd_tz_test"


async def test_get_due_cards_sorts_by_urgency(
    db: AsyncSession, user_with_timezone: User, deck_for_memory_states: Deck
):
    """Test that get_due_cards returns cards sorted by the due_at timestamp."""
    now_utc = datetime.now(pytz.utc)
    card1 = Flashcard(
        id="crd_urgency1", deck_id=deck_for_memory_states.id, question="Q1", answer="A1"
    )
    card2 = Flashcard(
        id="crd_urgency2", deck_id=deck_for_memory_states.id, question="Q2", answer="A2"
    )
    db.add_all([card1, card2])
    await db.flush()

    # State 2 is more urgent (due earlier)
    state1 = CardMemoryState(
        card_id=card1.id, user_id=user_with_timezone.id, due_at=now_utc - timedelta(days=1)
    )
    state2 = CardMemoryState(
        card_id=card2.id, user_id=user_with_timezone.id, due_at=now_utc - timedelta(days=2)
    )
    db.add_all([state1, state2])
    await db.commit()

    due_cards_result = await get_due_cards(db, user_with_timezone)
    due_cards = [item[0] for item in due_cards_result]  # Unpack tuple

    assert len(due_cards) == 2
    assert due_cards[0].card_id == "crd_urgency2"  # The most overdue card comes first
    assert due_cards[1].card_id == "crd_urgency1"


async def test_get_weak_spots(
    db: AsyncSession, user_with_timezone: User, deck_for_memory_states: Deck
):
    """Test that get_weak_spots returns cards with the lowest ease factors."""
    card1 = Flashcard(id="crd_weak1", deck_id=deck_for_memory_states.id, question="Q1", answer="A1")
    card2 = Flashcard(id="crd_weak2", deck_id=deck_for_memory_states.id, question="Q2", answer="A2")
    card3 = Flashcard(id="crd_weak3", deck_id=deck_for_memory_states.id, question="Q3", answer="A3")
    db.add_all([card1, card2, card3])
    await db.flush()

    # state2 is the "weakest" spot
    state1 = CardMemoryState(card_id=card1.id, user_id=user_with_timezone.id, ease_factor=2.5)
    state2 = CardMemoryState(card_id=card2.id, user_id=user_with_timezone.id, ease_factor=1.5)
    state3 = CardMemoryState(card_id=card3.id, user_id=user_with_timezone.id, ease_factor=2.0)
    db.add_all([state1, state2, state3])
    await db.commit()

    weak_spots_result = await get_weak_spots(db, user_with_timezone, limit=3)
    weak_spots = [item[0] for item in weak_spots_result]  # Unpack tuple

    assert len(weak_spots) == 3
    assert weak_spots[0].card_id == "crd_weak2"
    assert weak_spots[1].card_id == "crd_weak3"
    assert weak_spots[2].card_id == "crd_weak1"
