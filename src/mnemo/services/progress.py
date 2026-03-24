from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytz
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.models.card_memory_state import CardMemoryState
from mnemo.models.deck import Deck
from mnemo.models.flashcard import Flashcard
from mnemo.models.session import Session
from mnemo.models.session_card import SessionCard
from mnemo.models.user import User
from mnemo.utils.local_time import to_local_time

# A card's interval must reach this many days to be considered "mastered" (SM-2 convention).
MASTERY_INTERVAL_THRESHOLD = 21


def compute_accuracy(total: int, correct: int) -> float:
    if total == 0:
        return 0.0
    return round((correct / total) * 100.0, 2)


def compute_streak_from_datetimes(
    datetimes: Iterable[datetime],
    timezone_name: str,
    now: datetime | None = None,
) -> tuple[int, datetime | None, str | None]:
    """
    Compute a consecutive-day streak given a list of UTC datetimes and the user's timezone.

    ``now`` can be injected for deterministic testing; it defaults to the current
    wall-clock time in the user's timezone.  All date comparisons are performed in
    the user's local timezone so that day boundaries are respected correctly.

    Returns (streak_count, last_studied_at_utc, last_studied_at_local_iso).
    """
    try:
        tz = pytz.timezone(timezone_name)
    except Exception:
        tz = pytz.utc

    # Resolve "today" in the user's timezone.
    if now is None:
        today_local = datetime.now(tz).date()
    else:
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        today_local = now.astimezone(tz).date()

    # Convert study datetimes to local dates.
    local_dates: set[date] = set()
    last_dt: datetime | None = None
    for dt in datetimes:
        if dt is None:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        dt_local = dt.astimezone(tz)
        local_dates.add(dt_local.date())
        if last_dt is None or dt > last_dt:
            last_dt = dt

    if not local_dates:
        return 0, None, None

    most_recent_local = max(local_dates)

    # If the user hasn't studied today or yesterday the streak is broken.
    gap = (today_local - most_recent_local).days
    if gap > 1:
        streak = 0
    else:
        # Walk back from the most recent date that has a study entry.
        # Starting from today would yield 0 on days where the user hasn't
        # studied yet but yesterday's streak is still valid (gap == 1).
        streak = 0
        cursor = most_recent_local
        while cursor in local_dates:
            streak += 1
            cursor = cursor - timedelta(days=1)

    last_studied_local_iso = None
    if last_dt is not None:
        try:
            last_studied_local_iso = last_dt.astimezone(tz).isoformat()
        except Exception:
            last_studied_local_iso = last_dt.astimezone(pytz.utc).isoformat()

    return streak, last_dt, last_studied_local_iso


def _resolve_local_time(dt: datetime | None, timezone_name: str) -> str | None:
    """Return localized ISO string for `dt` in `timezone_name`, falling back to UTC on error.

    Returns None when `dt` is falsy.
    """
    if not dt:
        return None
    try:
        return to_local_time(dt, timezone_name)
    except Exception:
        try:
            return to_local_time(dt, "UTC")
        except Exception:
            return None


def _end_of_today_utc(timezone_name: str, now: datetime | None = None) -> datetime:
    """Return the end of today (23:59:59.999999) in the user's timezone, as a UTC datetime.

    ``now`` can be injected for deterministic testing; defaults to the current wall-clock time.
    """
    try:
        tz = pytz.timezone(timezone_name)
    except Exception:
        tz = pytz.utc
    if now is None:
        now_local = datetime.now(tz)
    else:
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        now_local = now.astimezone(tz)
    end_local = now_local.replace(hour=23, minute=59, second=59, microsecond=999999)
    return end_local.astimezone(pytz.utc)


async def _fetch_progress_aggregates(
    db: AsyncSession, user: User, deck_id: str | None = None
) -> tuple[int, int, datetime | None]:
    """Execute SQL aggregates for progress; optionally filter by deck_id.

    Returns (total_answered, correct_answers, last_studied_at).
    """
    stmt = (
        select(
            func.count(SessionCard.id).label("total_answered"),
            func.coalesce(func.sum(case((SessionCard.correct, 1), else_=0)), 0).label(
                "correct_answers"
            ),
            func.max(SessionCard.answered_at).label("last_studied_at"),
        )
        .join(Session, Session.id == SessionCard.session_id)
        .where(Session.user_id == user.id)
        .where(SessionCard.answered)
    )

    if deck_id is not None:
        stmt = stmt.where(Session.deck_id == deck_id)

    result = await db.execute(stmt)
    row = result.one()
    total_answered = int(row.total_answered or 0)
    correct_answers = int(row.correct_answers or 0)
    last_studied_dt = row.last_studied_at
    return total_answered, correct_answers, last_studied_dt


async def _count_total_cards(db: AsyncSession, user_id: str, deck_id: str | None = None) -> int:
    """Count flashcards in all decks (or a specific deck) belonging to the user."""
    stmt = (
        select(func.count(Flashcard.id))
        .join(Deck, Deck.id == Flashcard.deck_id)
        .where(Deck.user_id == user_id)
    )
    if deck_id is not None:
        stmt = stmt.where(Flashcard.deck_id == deck_id)
    result = await db.execute(stmt)
    return int(result.scalar() or 0)


async def _count_mastered_cards(db: AsyncSession, user_id: str, deck_id: str | None = None) -> int:
    """Count cards the user has mastered (interval_days >= threshold), optionally per deck."""
    stmt = (
        select(func.count(CardMemoryState.card_id))
        .join(Flashcard, Flashcard.id == CardMemoryState.card_id)
        .join(Deck, Deck.id == Flashcard.deck_id)
        .where(
            CardMemoryState.user_id == user_id,
            CardMemoryState.interval_days >= MASTERY_INTERVAL_THRESHOLD,
            Deck.user_id == user_id,
        )
    )
    if deck_id is not None:
        stmt = stmt.where(Flashcard.deck_id == deck_id)
    result = await db.execute(stmt)
    return int(result.scalar() or 0)


async def _count_due_today(
    db: AsyncSession, user_id: str, cutoff: datetime, deck_id: str | None = None
) -> int:
    """Count cards due by `cutoff` UTC, optionally filtered to a specific deck."""
    stmt = (
        select(func.count(CardMemoryState.card_id))
        .join(Flashcard, Flashcard.id == CardMemoryState.card_id)
        .join(Deck, Deck.id == Flashcard.deck_id)
        .where(
            CardMemoryState.user_id == user_id,
            CardMemoryState.due_at.isnot(None),
            CardMemoryState.due_at <= cutoff,
            Deck.user_id == user_id,
        )
    )
    if deck_id is not None:
        stmt = stmt.where(Flashcard.deck_id == deck_id)
    result = await db.execute(stmt)
    return int(result.scalar() or 0)


async def _count_total_sessions(db: AsyncSession, user_id: str, deck_id: str | None = None) -> int:
    """Count study sessions for the user, optionally filtered to a specific deck."""
    stmt = select(func.count(Session.id)).where(Session.user_id == user_id)
    if deck_id is not None:
        stmt = stmt.where(Session.deck_id == deck_id)
    result = await db.execute(stmt)
    return int(result.scalar() or 0)


async def _get_deck_summaries(
    db: AsyncSession, user_id: str, cutoff: datetime
) -> list[dict[str, Any]]:
    """Build per-deck summary rows for all decks belonging to the user."""
    decks_result = await db.execute(select(Deck).where(Deck.user_id == user_id))
    decks = decks_result.scalars().all()

    # Mastered counts per deck (single query)
    mastered_stmt = (
        select(Flashcard.deck_id, func.count(CardMemoryState.card_id).label("cnt"))
        .join(CardMemoryState, CardMemoryState.card_id == Flashcard.id)
        .join(Deck, Deck.id == Flashcard.deck_id)
        .where(
            CardMemoryState.user_id == user_id,
            CardMemoryState.interval_days >= MASTERY_INTERVAL_THRESHOLD,
            Deck.user_id == user_id,
        )
        .group_by(Flashcard.deck_id)
    )
    mastered_result = await db.execute(mastered_stmt)
    mastered_by_deck: dict[str, int] = {row.deck_id: int(row.cnt) for row in mastered_result}

    # Due counts per deck (single query)
    due_stmt = (
        select(Flashcard.deck_id, func.count(CardMemoryState.card_id).label("cnt"))
        .join(CardMemoryState, CardMemoryState.card_id == Flashcard.id)
        .join(Deck, Deck.id == Flashcard.deck_id)
        .where(
            CardMemoryState.user_id == user_id,
            CardMemoryState.due_at.isnot(None),
            CardMemoryState.due_at <= cutoff,
            Deck.user_id == user_id,
        )
        .group_by(Flashcard.deck_id)
    )
    due_result = await db.execute(due_stmt)
    due_by_deck: dict[str, int] = {row.deck_id: int(row.cnt) for row in due_result}

    summaries: list[dict[str, Any]] = []
    for deck in decks:
        total = deck.card_count or 0
        mastered = mastered_by_deck.get(deck.id, 0)
        due_count = due_by_deck.get(deck.id, 0)
        mastery_pct = round(mastered / total, 4) if total > 0 else 0.0
        summaries.append(
            {
                "deck_id": deck.id,
                "name": deck.name,
                "mastery_pct": mastery_pct,
                "due_count": due_count,
            }
        )
    return summaries


async def get_user_progress(db: AsyncSession, user: User) -> dict[str, Any]:
    """Get aggregate progress for a user, per spec section 09."""
    cutoff = _end_of_today_utc(user.timezone)

    total_answered, correct_answers, last_studied_dt = await _fetch_progress_aggregates(db, user)
    total_cards = await _count_total_cards(db, user.id)
    mastered_cards = await _count_mastered_cards(db, user.id)
    due_today = await _count_due_today(db, user.id, cutoff)
    total_sessions = await _count_total_sessions(db, user.id)
    deck_summaries = await _get_deck_summaries(db, user.id, cutoff)

    accuracy_rate = round(compute_accuracy(total_answered, correct_answers) / 100.0, 4)
    last_studied_at_local = _resolve_local_time(last_studied_dt, user.timezone)

    streak_datetimes = await _fetch_streak_datetimes(db, user.id)
    study_streak_days, _, _ = compute_streak_from_datetimes(streak_datetimes, user.timezone)

    return {
        "user_id": user.id,
        "total_cards": total_cards,
        "mastered_cards": mastered_cards,
        "due_today": due_today,
        "accuracy_rate": accuracy_rate,
        "study_streak_days": study_streak_days,
        "total_sessions": total_sessions,
        "last_studied_at": last_studied_dt,
        "last_studied_at_local": last_studied_at_local,
        "deck_summaries": deck_summaries,
    }


async def get_deck_progress(
    db: AsyncSession, user: User, deck_id: str | None = None, deck: Deck | None = None
) -> dict[str, Any]:
    """Get per-deck mastery breakdown for a user, per spec section 09.

    Accepts either a `deck_id` (string) or an already-loaded `deck` object. When a
    `deck` is provided it will be used instead of performing an additional DB
    lookup, avoiding duplicate reads. If both are provided, `deck` is preferred
    and its `id` will be used as the deck identifier.
    """
    cutoff = _end_of_today_utc(user.timezone)

    # Prefer the provided deck object to avoid an extra DB read; when a deck
    # object is provided its id, name and card_count are used. Only when
    # `deck` is None do we fall back to using the explicit `deck_id` value and
    # possibly loading the Deck from the database.
    if deck is not None:
        deck_id = deck.id
        deck_name = deck.name
        total_cards_in_deck = deck.card_count or 0
    else:
        # Fail fast when caller didn't provide either an id or a deck object.
        if deck_id is None:
            raise ValueError("get_deck_progress requires either `deck_id` or `deck`")

        # Scope the lookup to the requesting/target user to avoid exposing
        # another user's deck metadata.
        deck_result = await db.execute(
            select(Deck).where(Deck.id == deck_id, Deck.user_id == user.id)
        )
        deck = deck_result.scalar_one_or_none()
        deck_name = deck.name if deck else deck_id
        total_cards_in_deck = deck.card_count if deck else 0

    total_answered, correct_answers, last_studied_dt = await _fetch_progress_aggregates(
        db, user, deck_id=deck_id
    )
    mastered_cards = await _count_mastered_cards(db, user.id, deck_id=deck_id)
    due_count = await _count_due_today(db, user.id, cutoff, deck_id=deck_id)
    total_sessions = await _count_total_sessions(db, user.id, deck_id=deck_id)

    accuracy_rate = round(compute_accuracy(total_answered, correct_answers) / 100.0, 4)
    mastery_pct = round(mastered_cards / total_cards_in_deck, 4) if total_cards_in_deck > 0 else 0.0
    last_studied_at_local = _resolve_local_time(last_studied_dt, user.timezone)

    return {
        "deck_id": deck_id,
        "name": deck_name,
        "total_cards": total_cards_in_deck,
        "mastered_cards": mastered_cards,
        "mastery_pct": mastery_pct,
        "due_count": due_count,
        "accuracy_rate": accuracy_rate,
        "total_sessions": total_sessions,
        "last_studied_at": last_studied_dt,
        "last_studied_at_local": last_studied_at_local,
    }


async def _fetch_streak_datetimes(db: AsyncSession, user_id: str) -> list[datetime]:
    """Return all answered_at datetimes for the user's completed session cards."""
    stmt = (
        select(SessionCard.answered_at)
        .join(Session, Session.id == SessionCard.session_id)
        .where(Session.user_id == user_id)
        .where(SessionCard.answered)
    )
    result = await db.execute(stmt)
    return [dt for dt in result.scalars().all() if dt is not None]


async def get_user_streak(db: AsyncSession, user: User) -> dict[str, Any]:
    datetimes = await _fetch_streak_datetimes(db, user.id)
    streak, last_dt, last_local_iso = compute_streak_from_datetimes(datetimes, user.timezone)
    return {"streak": streak, "last_studied_at": last_dt, "last_studied_at_local": last_local_iso}
