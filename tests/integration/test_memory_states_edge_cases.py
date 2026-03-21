"""
Integration tests for edge cases in memory state services and endpoints.
"""

from datetime import datetime

import pytest
import pytz
from freezegun import freeze_time
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.models import CardMemoryState, Deck, Flashcard, User
from mnemo.services.spaced_repetition import get_due_cards, get_or_create_memory_state
from mnemo.utils.local_time import to_local_time

# Register shared fixtures
pytest_plugins = ["tests.test_fixtures"]

# Mark all tests in this module as async
pytestmark = pytest.mark.asyncio


@pytest.fixture
async def user_with_dst_timezone(db: AsyncSession, authenticated_user: User) -> User:
    """Use the authenticated_user fixture so the client's auth matches."""
    db.add(authenticated_user)
    await db.flush()
    return authenticated_user


@pytest.fixture
async def user_with_extreme_timezone(db: AsyncSession) -> User:
    user = User(
        id="usr_extreme_tz_tester",
        country="KI",
        timezone="Pacific/Kiritimati",
        display_name="Extreme Timezone Tester",
    )
    db.add(user)
    await db.flush()
    return user


@pytest.fixture
async def user_with_invalid_timezone(db: AsyncSession) -> User:
    user = User(
        id="usr_b2c3d4e5f6a7b8c9",
        country="AQ",
        timezone="Mars/Olympus_Mons",
        display_name="Invalid Timezone Tester",
    )
    db.add(user)
    await db.flush()
    return user


@pytest.fixture
async def deck_for_invalid_tz_user(db: AsyncSession, user_with_invalid_timezone: User) -> Deck:
    deck = Deck(
        id="dck_invalid_tz",
        name="Deck for Invalid TZ User",
        user_id=user_with_invalid_timezone.id,
    )
    db.add(deck)
    await db.flush()
    return deck


async def test_get_due_cards_with_invalid_timezone_falls_back_to_utc(
    db: AsyncSession, user_with_invalid_timezone: User, deck_for_invalid_tz_user: Deck
):
    now_utc = datetime.now(pytz.utc)
    card = Flashcard(
        id="crd_invalid_tz_test",
        deck_id=deck_for_invalid_tz_user.id,
        question="Invalid timezone test",
        answer="Falls back to UTC",
    )
    db.add(card)
    await db.flush()

    memory_state = CardMemoryState(
        card_id=card.id,
        user_id=user_with_invalid_timezone.id,
        due_at=now_utc,
    )
    db.add(memory_state)
    await db.flush()

    due_cards_result = await get_due_cards(db, user_with_invalid_timezone)
    due_cards = [item[0] for item in due_cards_result]

    assert len(due_cards) == 1
    assert due_cards[0].card_id == "crd_invalid_tz_test"


@pytest.fixture
async def deck_for_dst_user(db: AsyncSession, user_with_dst_timezone: User) -> Deck:
    deck = Deck(
        id="dck_dst_tz",
        name="Deck for DST User",
        user_id=user_with_dst_timezone.id,
    )
    db.add(deck)
    await db.flush()
    return deck


@freeze_time("2026-06-01 12:00:00")
async def test_get_due_cards_handles_dst_correctly(
    db: AsyncSession, user_with_dst_timezone: User, deck_for_dst_user: Deck
):
    user_tz = pytz.timezone(user_with_dst_timezone.timezone)
    dst_time = user_tz.localize(datetime(2026, 6, 1, 10, 0, 0))
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
    await db.flush()

    due_cards_result = await get_due_cards(db, user_with_dst_timezone)
    due_cards = [item[0] for item in due_cards_result]
    assert len(due_cards) == 1


@pytest.fixture
async def deck_for_extreme_tz_user(db: AsyncSession, user_with_extreme_timezone: User) -> Deck:
    deck = Deck(
        id="dck_extreme_tz",
        name="Deck for Extreme TZ User",
        user_id=user_with_extreme_timezone.id,
    )
    db.add(deck)
    await db.flush()
    return deck


@freeze_time("2023-01-09 11:00:00")
async def test_get_due_cards_handles_extreme_timezone_offset(
    db: AsyncSession, user_with_extreme_timezone: User, deck_for_extreme_tz_user: Deck
):
    user_tz = pytz.timezone(user_with_extreme_timezone.timezone)
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
    await db.flush()

    due_cards_result = await get_due_cards(db, user_with_extreme_timezone)
    due_cards = [item[0] for item in due_cards_result]
    assert len(due_cards) == 1
    assert due_cards[0].card_id == "crd_extreme_tz_test"


@freeze_time("2023-01-10 12:00:00")
async def test_get_due_cards_handles_midnight_boundary(
    db: AsyncSession, user_with_dst_timezone: User, deck_for_dst_user: Deck
):
    user_tz = pytz.timezone(user_with_dst_timezone.timezone)
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
    await db.flush()

    due_cards_result = await get_due_cards(db, user_with_dst_timezone)
    due_cards = [item[0] for item in due_cards_result]
    assert len(due_cards) == 1
    assert due_cards[0].card_id == "crd_midnight_test"


@freeze_time("2023-01-10 12:00:00")
async def test_due_at_local_updates_after_timezone_change(
    db: AsyncSession, user_with_dst_timezone: User, deck_for_dst_user: Deck
):
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
    await db.flush()

    user_with_dst_timezone.timezone = "America/Los_Angeles"
    db.add(user_with_dst_timezone)
    await db.flush()

    due_at_local = to_local_time(due_time_utc, user_with_dst_timezone.timezone)
    assert "-07:00" in due_at_local or "-08:00" in due_at_local


@freeze_time("2024-02-28 12:00:00")
async def test_due_date_calculation_handles_leap_years(
    db: AsyncSession, user_with_dst_timezone: User, deck_for_dst_user: Deck
):
    from datetime import timedelta

    from mnemo.services.spaced_repetition import update_memory_state_after_answer

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
        repetitions=2,
    )
    db.add(memory_state)
    await db.flush()

    updated_state = update_memory_state_after_answer(memory_state, 5)
    new_interval = updated_state.interval_days
    expected_due_date = start_date + timedelta(days=new_interval)
    assert updated_state.due_at.date() == expected_due_date.date()


async def test_get_memory_state_for_non_existent_card(
    db: AsyncSession,
    client: AsyncClient,
    user_with_dst_timezone: User,
):
    response = await client.get("/v1/cards/crd_non_existent/memory")
    assert response.status_code == 404


async def test_get_memory_state_for_new_card(
    db: AsyncSession,
    client: AsyncClient,
    user_with_dst_timezone: User,
    deck_for_dst_user: Deck,
):
    card = Flashcard(
        id="crd_new_card_test",
        deck_id=deck_for_dst_user.id,
        question="New card test",
        answer="Works",
    )
    db.add(card)
    await db.flush()

    response = await client.get(f"/v1/cards/{card.id}/memory")
    assert response.status_code == 200
    data = response.json()
    assert data["repetitions"] == 0
    assert data["streak"] == 0
    assert data["ease_factor"] == 2.5


async def test_get_due_cards_with_no_due_cards(
    client: AsyncClient,
    user_with_dst_timezone: User,
):
    response = await client.get(f"/v1/users/{user_with_dst_timezone.id}/due")
    assert response.status_code == 200
    data = response.json()
    assert data["due_count"] == 0
    assert data["cards"] == []


async def test_get_weak_spots_with_no_answered_cards(
    client: AsyncClient,
    user_with_dst_timezone: User,
):
    response = await client.get(f"/v1/users/{user_with_dst_timezone.id}/weak-spots")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 0
    assert data["cards"] == []


async def test_get_weak_spots_with_same_ease_factor(
    db: AsyncSession,
    client: AsyncClient,
    user_with_dst_timezone: User,
    deck_for_dst_user: Deck,
):
    card1 = Flashcard(id="crd_weak_same1", deck_id=deck_for_dst_user.id, question="Q1", answer="A1")
    card2 = Flashcard(id="crd_weak_same2", deck_id=deck_for_dst_user.id, question="Q2", answer="A2")
    db.add_all([card1, card2])
    await db.flush()

    state1 = CardMemoryState(card_id=card1.id, user_id=user_with_dst_timezone.id, ease_factor=2.5)
    state2 = CardMemoryState(card_id=card2.id, user_id=user_with_dst_timezone.id, ease_factor=2.5)
    db.add_all([state1, state2])
    await db.flush()

    response = await client.get(f"/v1/users/{user_with_dst_timezone.id}/weak-spots")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2


async def test_get_weak_spots_with_limit(
    db: AsyncSession,
    client: AsyncClient,
    user_with_dst_timezone: User,
    deck_for_dst_user: Deck,
):
    card1 = Flashcard(
        id="crd_weak_limit1", deck_id=deck_for_dst_user.id, question="Q1", answer="A1"
    )
    card2 = Flashcard(
        id="crd_weak_limit2", deck_id=deck_for_dst_user.id, question="Q2", answer="A2"
    )
    db.add_all([card1, card2])
    await db.flush()

    state1 = CardMemoryState(card_id=card1.id, user_id=user_with_dst_timezone.id, ease_factor=1.5)
    state2 = CardMemoryState(card_id=card2.id, user_id=user_with_dst_timezone.id, ease_factor=2.5)
    db.add_all([state1, state2])
    await db.flush()

    response = await client.get(f"/v1/users/{user_with_dst_timezone.id}/weak-spots?limit=1")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["cards"][0]["id"] == "crd_weak_limit1"


async def test_answer_card_with_invalid_score(
    db: AsyncSession,
    client: AsyncClient,
    user_with_dst_timezone: User,
    deck_for_dst_user: Deck,
):
    card = Flashcard(
        id="crd_invalid_score_test",
        deck_id=deck_for_dst_user.id,
        question="Invalid score test",
        answer="Works",
    )
    db.add(card)
    await db.flush()

    response = await client.post(f"/v1/cards/{card.id}/answer", json={"score": 6})
    assert response.status_code == 422


@pytest.mark.skipif(
    "sqlite" in str(__import__("mnemo.db.database", fromlist=["engine"]).engine.url.drivername),
    reason="SQLite cannot handle concurrent savepoints on a single connection",
)
async def test_concurrent_answers(
    db: AsyncSession,
    client: AsyncClient,
    user_with_dst_timezone: User,
    deck_for_dst_user: Deck,
):
    import asyncio

    card = Flashcard(
        id="crd_concurrent_test",
        deck_id=deck_for_dst_user.id,
        question="Concurrent test",
        answer="Works",
    )
    db.add(card)
    await db.flush()

    await get_or_create_memory_state(db, card.id, deck_for_dst_user.user_id)
    await db.flush()

    tasks = [client.post(f"/v1/cards/{card.id}/answer", json={"score": 5}) for _ in range(2)]
    responses = await asyncio.gather(*tasks)
    assert all(response.status_code == 200 for response in responses)

    db.expire_all()
    final_memory_state = await get_or_create_memory_state(db, card.id, deck_for_dst_user.user_id)
    assert final_memory_state is not None
    assert final_memory_state.repetitions == 2
    assert final_memory_state.streak == 2


async def test_orphaned_memory_states_are_deleted(
    db: AsyncSession, user_with_dst_timezone: User, deck_for_dst_user: Deck
):
    card = Flashcard(
        id="crd_orphan_test",
        deck_id=deck_for_dst_user.id,
        question="Orphan test",
        answer="Works",
    )
    db.add(card)
    await db.flush()

    memory_state = CardMemoryState(card_id=card.id, user_id=user_with_dst_timezone.id)
    db.add(memory_state)
    await db.flush()

    user_id = user_with_dst_timezone.id
    card_id = card.id

    await db.delete(card)
    await db.flush()
    db.expire_all()

    statement = select(CardMemoryState).where(
        CardMemoryState.card_id == card_id,
        CardMemoryState.user_id == user_id,
    )
    result = await db.execute(statement)
    assert result.scalar_one_or_none() is None


async def test_duplicate_memory_states_are_prevented(
    db: AsyncSession, user_with_dst_timezone: User, deck_for_dst_user: Deck
):
    from sqlalchemy.exc import IntegrityError

    card = Flashcard(
        id="crd_duplicate_test",
        deck_id=deck_for_dst_user.id,
        question="Duplicate test",
        answer="Works",
    )
    db.add(card)
    await db.flush()

    memory_state1 = CardMemoryState(card_id=card.id, user_id=user_with_dst_timezone.id)
    db.add(memory_state1)
    await db.flush()

    memory_state2 = CardMemoryState(card_id=card.id, user_id=user_with_dst_timezone.id)
    db.add(memory_state2)
    with pytest.raises(IntegrityError):
        await db.flush()
