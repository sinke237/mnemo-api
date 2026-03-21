"""
Study plan service.
Generates and retrieves day-by-day study schedules per spec FR-07.2.

Schedule generation accounts for:
- The deck's total card count
- The user's daily time availability (daily_minutes)
- A simple spaced-repetition review estimate (SM-2 inspired)
- The user's country-derived timezone for local date labels (FR-07.2)
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from math import ceil
from typing import Any

import pytz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.core.exceptions import DeckNotFoundError, PlanNotFoundError
from mnemo.models.deck import Deck
from mnemo.models.study_plan import StudyPlan
from mnemo.models.user import User
from mnemo.utils.id_generator import generate_plan_id

# Rough estimate: average minutes to study one flashcard (new + review)
_MINUTES_PER_CARD = 2

# Per SM-2: after first study, a fraction of cards is estimated to return each
# subsequent day as spaced repetition reviews.
_DAILY_REVIEW_FACTOR = 0.25


def _today_in_timezone(timezone_name: str, now: datetime | None = None) -> date:
    """Return today's date in the user's local timezone."""
    try:
        tz = pytz.timezone(timezone_name)
    except pytz.UnknownTimeZoneError:
        tz = pytz.utc
    if now is None:
        return datetime.now(tz).date()
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return now.astimezone(tz).date()


def generate_schedule(
    total_cards: int,
    days: int,
    daily_target: int,
    max_cards_per_day: int,
    start_date: date,
    deck_name: str,
) -> list[dict[str, Any]]:
    """
    Build a day-by-day schedule list.

    daily_target  -- new cards introduced each day
    max_cards_per_day -- upper bound from time budget
    start_date    -- first day of the plan (in user's local timezone, FR-07.2)
    """
    schedule: list[dict[str, Any]] = []
    remaining_new = total_cards
    studied_cumulative = 0

    for d in range(1, days + 1):
        day_date = start_date + timedelta(days=d - 1)

        new_cards = min(daily_target, remaining_new)
        remaining_new -= new_cards

        # Estimate review load: a fraction of all cards studied so far recycle
        # each subsequent day (simplified SM-2 first-interval approximation).
        review_estimate = int(studied_cumulative * _DAILY_REVIEW_FACTOR) if d > 1 else 0

        cards_to_study = min(new_cards + review_estimate, max_cards_per_day)
        studied_cumulative += new_cards

        # Build a human-readable focus label
        if d == 1:
            focus = f"New cards: introduction to {deck_name}"
        elif new_cards > 0 and review_estimate > 0:
            if d == 2:
                focus = "New cards plus first round of reviews"
            else:
                focus = "New cards plus review of previous material"
        elif new_cards > 0:
            focus = "New cards: covering remaining material"
        else:
            focus = "Review and consolidation"

        schedule.append(
            {
                "day": d,
                "date": day_date.isoformat(),
                "cards_to_study": cards_to_study,
                "focus": focus,
            }
        )

    return schedule


async def create_plan(
    db: AsyncSession,
    user: User,
    deck_id: str,
    goal: str | None,
    days: int,
    daily_minutes: int,
    now: datetime | None = None,
) -> StudyPlan:
    """
    Generate a new study plan for *user* around *deck_id*.

    Raises DeckNotFoundError if the deck does not belong to the user.
    """
    result = await db.execute(select(Deck).where(Deck.id == deck_id, Deck.user_id == user.id))
    deck = result.scalar_one_or_none()
    if deck is None:
        raise DeckNotFoundError(deck_id=deck_id)

    total_cards = deck.card_count or 0

    if days <= 0:
        raise ValueError(f"days must be a positive integer, got {days}")
    if daily_minutes <= 0:
        raise ValueError(f"daily_minutes must be a positive integer, got {daily_minutes}")

    # How many cards can the user realistically study per day given their time?
    # If there are cards to study, ensure the time budget yields at least one
    # card per day to avoid feeding a zero `max_cards_per_day` into
    # `generate_schedule` which would result in zero `cards_to_study`.
    max_by_time = daily_minutes // _MINUTES_PER_CARD
    if total_cards > 0:
        max_by_time = max(1, max_by_time)

    # How many new cards must be introduced per day to cover all cards within
    # the requested window?
    target_by_coverage = ceil(total_cards / days) if total_cards > 0 else 1

    # daily_target drives how many *new* cards are introduced per day; it must
    # not exceed the time budget (reviews on top would otherwise overflow).
    daily_target = min(target_by_coverage, max_by_time)
    daily_target = max(daily_target, 1)

    start_date = _today_in_timezone(user.timezone, now)
    schedule = generate_schedule(
        total_cards=total_cards,
        days=days,
        daily_target=daily_target,
        max_cards_per_day=max_by_time,
        start_date=start_date,
        deck_name=deck.name,
    )

    plan = StudyPlan(
        id=generate_plan_id(),
        user_id=user.id,
        deck_id=deck_id,
        goal=goal,
        days=days,
        daily_target=daily_target,
        daily_minutes=daily_minutes,
        schedule=schedule,
    )
    # Set created_at explicitly to avoid DB-second-resolution ties when
    # multiple plans are created rapidly in the same test/request flow.
    plan.created_at = datetime.now(UTC)
    db.add(plan)
    await db.flush()
    await db.refresh(plan)
    return plan


async def get_active_plan(db: AsyncSession, user_id: str) -> StudyPlan:
    """
    Return the most recently created plan for *user_id*.

    Raises PlanNotFoundError when no plan exists.
    """
    result = await db.execute(
        select(StudyPlan)
        .where(StudyPlan.user_id == user_id)
        .order_by(StudyPlan.created_at.desc(), StudyPlan.id.desc())
        .limit(1)
    )
    plan = result.scalar_one_or_none()
    if plan is None:
        raise PlanNotFoundError(f"No active study plan for user: {user_id}")
    return plan
