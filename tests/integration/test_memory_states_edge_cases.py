"""
Integration tests for edge cases in memory state services and endpoints.
"""

from collections.abc import AsyncIterator
from datetime import datetime

import pytest
import pytz
from freezegun import freeze_time
from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.core.constants import PermissionScope
from mnemo.db.database import AsyncSessionLocal
from mnemo.models import CardMemoryState, Deck, Flashcard, User
from mnemo.services.api_key import create_api_key
from mnemo.services.spaced_repetition import get_due_cards, get_or_create_memory_state

# Register shared fixtures
pytest_plugins = ["tests.test_fixtures"]

# Mark all tests in this module as async
pytestmark = pytest.mark.asyncio


@pytest.fixture
async def user_with_invalid_timezone(db: AsyncSession) -> User:
    """Fixture for a user with an invalid timezone."""
    user = User(
        id="usr_a1b2c3d4e5f6a7b8",
        country="AQ",  # Antarctica
        timezone="Mars/Olympus_Mons",
        display_name="Invalid Timezone Tester",
    )
    db.add(user)
    await db.commit()
    return user


@pytest.fixture
async def deck_for_invalid_tz_user(db: AsyncSession, user_with_invalid_timezone: User) -> Deck:
    """Fixture for a deck for the user with an invalid timezone."""
    deck = Deck(
        id="dck_invalid_tz",
        name="Deck for Invalid TZ User",
        user_id=user_with_invalid_timezone.id,
    )
    db.add(deck)
    await db.commit()
    return deck


async def test_get_due_cards_with_invalid_timezone_falls_back_to_utc(
    db: AsyncSession, user_with_invalid_timezone: User, deck_for_invalid_tz_user: Deck
):
    """Test that get_due_cards falls back to UTC for a user with an invalid timezone."""
    now_utc = datetime.now(pytz.utc)
    card = Flashcard(
        id="crd_invalid_tz_test",
        deck_id=deck_for_invalid_tz_user.id,
        question="Invalid timezone test",
        answer="Falls back to UTC",
    )
    db.add(card)
    await db.flush()

    # This card is due today in UTC, but would not be if the invalid timezone was used.
    memory_state = CardMemoryState(
        card_id=card.id,
        user_id=user_with_invalid_timezone.id,
        due_at=now_utc,
    )
    db.add(memory_state)
    await db.commit()

    due_cards_result = await get_due_cards(db, user_with_invalid_timezone)
    due_cards = [item[0] for item in due_cards_result]

    assert len(due_cards) == 1
    assert due_cards[0].card_id == "crd_invalid_tz_test"


@pytest.fixture
async def deck_for_dst_user(db: AsyncSession, user_with_dst_timezone: User) -> Deck:
    """Fixture for a deck for the user with a DST timezone."""
    deck = Deck(
        id="dck_dst_tz",
        name="Deck for DST User",
        user_id=user_with_dst_timezone.id,
    )
    db.add(deck)
    await db.commit()
    return deck


@freeze_time("2026-06-01 12:00:00")
async def test_get_due_cards_handles_dst_correctly(
    db: AsyncSession, user_with_dst_timezone: User, deck_for_dst_user: Deck
):
    """Test that get_due_cards handles Daylight Saving Time correctly."""
    user_tz = pytz.timezone(user_with_dst_timezone.timezone)

    # A time that is during DST in America/New_York
    dst_time = datetime(2026, 6, 1, 10, 0, 0, tzinfo=user_tz)
    due_time_utc = dst_time.astimezone(pytz.utc)

    card = Flashcard(
        id="crd_dst_test",
        deck_id=deck_for_dst_user.id,
        question="DST test",
        answer="Works",
    )
    db.add(card)
    await db.flush()

    memory_state = CardMemoryState(
        card_id=card.id,
        user_id=user_with_dst_timezone.id,
        due_at=due_time_utc,
    )
    db.add(memory_state)
    await db.commit()

    due_cards_result = await get_due_cards(db, user_with_dst_timezone)
    due_cards = [item[0] for item in due_cards_result]

    assert len(due_cards) == 1


@pytest.fixture
async def deck_for_extreme_tz_user(db: AsyncSession, user_with_extreme_timezone: User) -> Deck:
    """Fixture for a deck for the user with an extreme timezone."""
    deck = Deck(
        id="dck_extreme_tz",
        name="Deck for Extreme TZ User",
        user_id=user_with_extreme_timezone.id,
    )
    db.add(deck)
    await db.commit()
    return deck


async def test_get_due_cards_handles_extreme_timezone_offset(
    db: AsyncSession, user_with_extreme_timezone: User, deck_for_extreme_tz_user: Deck
):
    """Test that get_due_cards handles extreme timezone offsets correctly."""
    user_tz = pytz.timezone(user_with_extreme_timezone.timezone)

    # A time that is early in the day in the user's local time (UTC+14)
    local_time = datetime.now(user_tz).replace(hour=1, minute=0, second=0)
    due_time_utc = local_time.astimezone(pytz.utc)

    card = Flashcard(
        id="crd_extreme_tz_test",
        deck_id=deck_for_extreme_tz_user.id,
        question="Extreme timezone test",
        answer="Works",
    )
    db.add(card)
    await db.flush()

    memory_state = CardMemoryState(
        card_id=card.id,
        user_id=user_with_extreme_timezone.id,
        due_at=due_time_utc,
    )
    db.add(memory_state)
    await db.commit()

    due_cards_result = await get_due_cards(db, user_with_extreme_timezone)
    due_cards = [item[0] for item in due_cards_result]

    assert len(due_cards) == 1
    assert due_cards[0].card_id == "crd_extreme_tz_test"


async def test_get_due_cards_handles_midnight_boundary(
    db: AsyncSession, user_with_dst_timezone: User, deck_for_dst_user: Deck
):
    """Test that get_due_cards correctly handles the midnight boundary."""
    user_tz = pytz.timezone(user_with_dst_timezone.timezone)

    # A time just before midnight in the user's local time
    just_before_midnight_local = datetime.now(user_tz).replace(hour=23, minute=59, second=59)
    due_time_utc = just_before_midnight_local.astimezone(pytz.utc)

    card = Flashcard(
        id="crd_midnight_test",
        deck_id=deck_for_dst_user.id,
        question="Midnight boundary test",
        answer="Works",
    )
    db.add(card)
    await db.flush()

    memory_state = CardMemoryState(
        card_id=card.id,
        user_id=user_with_dst_timezone.id,
        due_at=due_time_utc,
    )
    db.add(memory_state)
    await db.commit()

    due_cards_result = await get_due_cards(db, user_with_dst_timezone)
    due_cards = [item[0] for item in due_cards_result]

    assert len(due_cards) == 1
    assert due_cards[0].card_id == "crd_midnight_test"


async def test_due_at_local_updates_after_timezone_change(
    db: AsyncSession, user_with_dst_timezone: User, deck_for_dst_user: Deck
):
    """Test that the due_at_local field reflects a user's timezone change."""
    user_tz = pytz.timezone(user_with_dst_timezone.timezone)
    due_time_local = datetime.now(user_tz).replace(hour=12, minute=0, second=0)
    due_time_utc = due_time_local.astimezone(pytz.utc)

    card = Flashcard(
        id="crd_tz_change_test",
        deck_id=deck_for_dst_user.id,
        question="Timezone change test",
        answer="Works",
    )
    db.add(card)
    await db.flush()

    memory_state = CardMemoryState(
        card_id=card.id,
        user_id=user_with_dst_timezone.id,
        due_at=due_time_utc,
    )
    db.add(memory_state)
    await db.commit()

    # Change the user's timezone
    user_with_dst_timezone.timezone = "America/Los_Angeles"
    db.add(user_with_dst_timezone)
    await db.commit()

    # The due_at_local should now be different
    from mnemo.utils.local_time import to_local_time

    due_at_local = to_local_time(due_time_utc, user_with_dst_timezone.timezone)
    assert "-07:00" in due_at_local or "-08:00" in due_at_local  # PDT or PST


@freeze_time("2024-02-28 12:00:00")
async def test_due_date_calculation_handles_leap_years(
    db: AsyncSession, user_with_dst_timezone: User, deck_for_dst_user: Deck
):
    """Test that the due date calculation is correct across a leap year."""
    from datetime import timedelta

    from mnemo.services.spaced_repetition import update_memory_state_after_answer

    # A date before a leap day
    start_date = datetime(2024, 2, 28, 12, 0, 0, tzinfo=pytz.utc)

    card = Flashcard(
        id="crd_leap_year_test",
        deck_id=deck_for_dst_user.id,
        question="Leap year test",
        answer="Works",
    )
    db.add(card)
    await db.flush()

    memory_state = CardMemoryState(
        card_id=card.id,
        user_id=user_with_dst_timezone.id,
        due_at=start_date,
        interval_days=1,
        repetitions=2,  # To trigger the interval calculation
    )
    db.add(memory_state)
    await db.commit()

    # Answer the card correctly, with an interval that will span the leap day
    updated_state = update_memory_state_after_answer(memory_state, 5)

    # The new due date should be start_date + interval_days
    # The SM-2 implementation will calculate the new interval
    new_interval = updated_state.interval_days
    expected_due_date = start_date + timedelta(days=new_interval)

    assert updated_state.due_at.date() == expected_due_date.date()


async def test_get_memory_state_for_non_existent_card(client, headers_for_user_with_dst_timezone):
    """Test getting the memory state for a non-existent card."""
    response = await client.get(
        "/v1/cards/crd_non_existent/memory", headers=headers_for_user_with_dst_timezone
    )
    assert response.status_code == 404


@pytest.fixture
async def db_session(
    client: AsyncClient,
) -> AsyncIterator[AsyncSession]:  # client is included to ensure tables are created
    async with AsyncSessionLocal() as session:
        yield session
        await session.commit()

        await session.execute(delete(CardMemoryState))
        await session.execute(delete(Flashcard))
        await session.execute(delete(Deck))
        await session.execute(delete(User))
        await session.commit()


@pytest.fixture
async def headers_for_user_with_dst_timezone(
    db_session: AsyncSession, client: AsyncClient, user_with_dst_timezone: User
) -> dict[str, str]:
    """Returns headers for the user with a DST timezone."""
    _, plain_key = await create_api_key(
        db=db_session,
        user_id=user_with_dst_timezone.id,
        name="Test Key",
        is_live=False,
        scopes=[
            PermissionScope.DECKS_READ,
            PermissionScope.DECKS_WRITE,
            PermissionScope.PROGRESS_READ,
        ],
    )
    await db_session.commit()

    token_response = await client.post(
        "/v1/auth/token",
        json={"user_id": user_with_dst_timezone.id, "api_key": plain_key},
    )
    assert token_response.status_code == 200
    token = token_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def test_get_memory_state_for_new_card(
    db_session: AsyncSession,
    client: AsyncClient,
    headers_for_user_with_dst_timezone: dict[str, str],
    deck_for_dst_user: Deck,
):
    """Test getting the memory state for a new, unanswered card."""
    card = Flashcard(
        id="crd_new_card_test",
        deck_id=deck_for_dst_user.id,
        question="New card test",
        answer="Works",
    )
    db_session.add(card)
    await db_session.commit()

    response = await client.get(
        f"/v1/cards/{card.id}/memory", headers=headers_for_user_with_dst_timezone
    )
    assert response.status_code == 200
    data = response.json()
    assert data["repetitions"] == 0
    assert data["streak"] == 0
    assert data["ease_factor"] == 2.5


async def test_get_due_cards_with_no_due_cards(
    client: AsyncClient,
    headers_for_user_with_dst_timezone: dict[str, str],
    user_with_dst_timezone: User,
):
    """Test the /due endpoint when the user has no due cards."""
    response = await client.get(
        f"/v1/users/{user_with_dst_timezone.id}/due", headers=headers_for_user_with_dst_timezone
    )
    assert response.status_code == 200
    data = response.json()
    assert data["due_count"] == 0
    assert data["cards"] == []


async def test_get_weak_spots_with_no_answered_cards(
    client: AsyncClient,
    headers_for_user_with_dst_timezone: dict[str, str],
    user_with_dst_timezone: User,
):
    """Test the /weak-spots endpoint when the user has no answered cards."""
    # Use the actual user object from the fixture
    response = await client.get(
        f"/v1/users/{user_with_dst_timezone.id}/weak-spots",
        headers=headers_for_user_with_dst_timezone,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 0
    assert data["cards"] == []


async def test_get_weak_spots_with_same_ease_factor(
    db_session: AsyncSession,
    client: AsyncClient,
    headers_for_user_with_dst_timezone: dict[str, str],
    deck_for_dst_user: Deck,
):
    """Test the /weak-spots endpoint when all cards have the same ease factor."""
    card1 = Flashcard(
        id="crd_weak_same1",
        deck_id=deck_for_dst_user.id,
        question="Q1",
        answer="A1",
    )
    card2 = Flashcard(
        id="crd_weak_same2",
        deck_id=deck_for_dst_user.id,
        question="Q2",
        answer="A2",
    )
    db_session.add_all([card1, card2])
    await db_session.flush()

    state1 = CardMemoryState(card_id=card1.id, user_id=deck_for_dst_user.user_id, ease_factor=2.5)
    state2 = CardMemoryState(card_id=card2.id, user_id=deck_for_dst_user.user_id, ease_factor=2.5)
    db_session.add_all([state1, state2])
    await db_session.commit()

    response = await client.get(
        f"/v1/users/{deck_for_dst_user.user_id}/weak-spots",
        headers=headers_for_user_with_dst_timezone,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2
    # The order is not guaranteed, so we don't assert on it.


async def test_get_weak_spots_with_limit(
    db_session: AsyncSession,
    client: AsyncClient,
    headers_for_user_with_dst_timezone: dict[str, str],
    deck_for_dst_user: Deck,
):
    """Test the limit parameter of the /weak-spots endpoint."""
    card1 = Flashcard(
        id="crd_weak_limit1",
        deck_id=deck_for_dst_user.id,
        question="Q1",
        answer="A1",
    )
    card2 = Flashcard(
        id="crd_weak_limit2",
        deck_id=deck_for_dst_user.id,
        question="Q2",
        answer="A2",
    )
    db_session.add_all([card1, card2])
    await db_session.flush()

    state1 = CardMemoryState(card_id=card1.id, user_id=deck_for_dst_user.user_id, ease_factor=1.5)
    state2 = CardMemoryState(card_id=card2.id, user_id=deck_for_dst_user.user_id, ease_factor=2.5)
    db_session.add_all([state1, state2])
    await db_session.commit()

    response = await client.get(
        f"/v1/users/{deck_for_dst_user.user_id}/weak-spots?limit=1",
        headers=headers_for_user_with_dst_timezone,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["cards"][0]["id"] == "crd_weak_limit1"


async def test_answer_card_with_invalid_score(
    db_session: AsyncSession,
    client: AsyncClient,
    headers_for_user_with_dst_timezone: dict[str, str],
    deck_for_dst_user: Deck,
):
    """Test the /answer endpoint with an invalid score."""
    card = Flashcard(
        id="crd_invalid_score_test",
        deck_id=deck_for_dst_user.id,
        question="Invalid score test",
        answer="Works",
    )
    db_session.add(card)
    await db_session.commit()

    response = await client.post(
        f"/v1/cards/{card.id}/answer",
        headers=headers_for_user_with_dst_timezone,
        json={"score": 6},
    )
    assert response.status_code == 422


async def test_concurrent_answers(
    db_session: AsyncSession,
    client: AsyncClient,
    headers_for_user_with_dst_timezone: dict[str, str],
    deck_for_dst_user: Deck,
):
    """Test submitting concurrent answers for the same card."""
    import asyncio

    card = Flashcard(
        id="crd_concurrent_test",
        deck_id=deck_for_dst_user.id,
        question="Concurrent test",
        answer="Works",
    )
    db_session.add(card)
    await db_session.commit()

    # Ensure the memory state is created before concurrent answers
    await get_or_create_memory_state(db_session, card.id, deck_for_dst_user.user_id)

    tasks = [
        client.post(
            f"/v1/cards/{card.id}/answer",
            headers=headers_for_user_with_dst_timezone,
            json={"score": 5},
        )
        for _ in range(2)
    ]
    responses = await asyncio.gather(*tasks)

    assert all(response.status_code == 200 for response in responses)


async def test_orphaned_memory_states_are_deleted(
    db: AsyncSession, user_with_dst_timezone: User, deck_for_dst_user: Deck
):
    """Test that orphaned memory states are deleted when a card is deleted."""
    card = Flashcard(
        id="crd_orphan_test",
        deck_id=deck_for_dst_user.id,
        question="Orphan test",
        answer="Works",
    )
    db.add(card)
    await db.flush()

    memory_state = CardMemoryState(
        card_id=card.id,
        user_id=user_with_dst_timezone.id,
    )
    db.add(memory_state)
    await db.commit()

    user_id = user_with_dst_timezone.id
    card_id = card.id

    # Delete the card
    await db.delete(card)
    await db.commit()
    db.expire_all()

    # The memory state should also be deleted
    statement = select(CardMemoryState).where(
        CardMemoryState.card_id == card_id,
        CardMemoryState.user_id == user_id,
    )
    result = await db.execute(statement)
    assert result.scalar_one_or_none() is None


async def test_duplicate_memory_states_are_prevented(
    db: AsyncSession, user_with_dst_timezone: User, deck_for_dst_user: Deck
):
    """Test that the database prevents the creation of duplicate memory states."""
    from sqlalchemy.exc import IntegrityError

    card = Flashcard(
        id="crd_duplicate_test",
        deck_id=deck_for_dst_user.id,
        question="Duplicate test",
        answer="Works",
    )
    db.add(card)
    await db.flush()

    memory_state1 = CardMemoryState(
        card_id=card.id,
        user_id=user_with_dst_timezone.id,
    )
    db.add(memory_state1)
    await db.commit()

    memory_state2 = CardMemoryState(
        card_id=card.id,
        user_id=user_with_dst_timezone.id,
    )
    db.add(memory_state2)
    with pytest.raises(IntegrityError):
        await db.commit()


@pytest.fixture
async def user_with_dst_timezone(db: AsyncSession) -> User:
    """Fixture for a user with a timezone that observes DST."""
    user = User(
        id="usr_b2c3d4e5f6a7b8a1",
        country="US",
        timezone="America/New_York",
        display_name="DST Timezone Tester",
    )
    db.add(user)
    await db.commit()
    return user


@pytest.fixture
async def user_with_extreme_timezone(db: AsyncSession) -> User:
    """Fixture for a user with an extreme timezone offset."""
    user = User(
        id="usr_c3d4e5f6a7b8a1b2",
        country="KI",  # Kiribati
        timezone="Pacific/Kiritimati",  # UTC+14
        display_name="Extreme Timezone Tester",
    )
    db.add(user)
    await db.commit()
    return user
