import math
from datetime import UTC, datetime, timedelta

import pytz
from sqlalchemy import Row, select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.core.constants import (
    DEFAULT_EASE_FACTOR,
    MIN_EASE_FACTOR,
    PASSING_SCORE,
)
from mnemo.models.card_memory_state import CardMemoryState
from mnemo.models.flashcard import Flashcard
from mnemo.models.user import User


async def get_or_create_memory_state(
    db: AsyncSession, card_id: str, user_id: str
) -> CardMemoryState | None:
    """Get or create a memory state for a card and user."""
    # First, check if the flashcard exists
    flashcard_exists = await db.scalar(select(Flashcard.id).where(Flashcard.id == card_id))
    if not flashcard_exists:
        return None

    statement = (
        select(CardMemoryState)
        .where(CardMemoryState.card_id == card_id, CardMemoryState.user_id == user_id)
        .with_for_update()
    )
    result = await db.execute(statement)
    memory_state = result.scalar_one_or_none()

    if not memory_state:
        memory_state = CardMemoryState(
            card_id=card_id,
            user_id=user_id,
            ease_factor=DEFAULT_EASE_FACTOR,
            repetitions=0,
            interval_days=0,
            streak=0,
        )
        db.add(memory_state)

    return memory_state


def update_memory_state_after_answer(memory_state: CardMemoryState, score: int) -> CardMemoryState:
    """
    Update the memory state of a card based on the SM-2 algorithm.
    This function is pure and does not commit to the DB.
    The caller is responsible for session management.
    """
    # Update ease factor based on the score.
    new_ease_factor = memory_state.ease_factor + (0.1 - (5 - score) * (0.08 + (5 - score) * 0.02))
    memory_state.ease_factor = max(MIN_EASE_FACTOR, new_ease_factor)

    if score < PASSING_SCORE:
        # Incorrect response. Reset progress.
        memory_state.repetitions = 0
        memory_state.streak = 0
        memory_state.interval_days = 1
    else:
        # Correct response. Update interval based on repetition number.
        if memory_state.repetitions == 0:
            memory_state.interval_days = 1
        elif memory_state.repetitions == 1:
            memory_state.interval_days = 6
        else:
            # The interval from the previous step is stored in interval_days.
            # Fallback to 6 if it's somehow not set.
            current_interval = (
                6 if memory_state.interval_days is None else memory_state.interval_days
            )
            memory_state.interval_days = math.ceil(current_interval * memory_state.ease_factor)

        memory_state.repetitions += 1
        memory_state.streak += 1

    # Set the next due date and record the last score.
    if memory_state.interval_days is not None:
        memory_state.due_at = datetime.now(UTC) + timedelta(days=memory_state.interval_days)
    memory_state.last_score = score

    return memory_state


async def get_due_cards(
    db: AsyncSession, user: User
) -> list[Row[tuple[CardMemoryState, Flashcard]]]:
    """
    Get all cards that are due for review for a user.
    "Due" means the due date is anytime up to the end of the current day
    in the user's local timezone.
    """
    try:
        user_tz = pytz.timezone(user.timezone)
    except pytz.UnknownTimeZoneError:
        user_tz = pytz.utc  # Fallback to UTC if timezone is invalid

    now_local = datetime.now(user_tz)
    end_of_today_local = now_local.replace(hour=23, minute=59, second=59, microsecond=999999)
    end_of_today_utc = end_of_today_local.astimezone(pytz.utc)

    statement = (
        select(CardMemoryState, Flashcard)
        .join(Flashcard, CardMemoryState.card_id == Flashcard.id)
        .where(CardMemoryState.user_id == user.id)
        .where(CardMemoryState.due_at <= end_of_today_utc)
        .order_by(CardMemoryState.due_at.asc())
    )
    result = await db.execute(statement)
    return list(result.all())


async def get_weak_spots(
    db: AsyncSession, user: User, limit: int
) -> list[Row[tuple[CardMemoryState, Flashcard]]]:
    """Get the cards with the lowest ease factor for a user."""
    statement = (
        select(CardMemoryState, Flashcard)
        .join(Flashcard, CardMemoryState.card_id == Flashcard.id)
        .where(CardMemoryState.user_id == user.id)
        .order_by(CardMemoryState.ease_factor.asc())
        .limit(limit)
    )
    result = await db.execute(statement)
    return list(result.all())
