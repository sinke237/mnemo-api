from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytz
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.models.session import Session
from mnemo.models.session_card import SessionCard
from mnemo.models.user import User
from mnemo.utils.local_time import to_local_time


def compute_accuracy(total: int, correct: int) -> float:
    if total == 0:
        return 0.0
    return round((correct / total) * 100.0, 2)


def compute_streak_from_datetimes(
    datetimes: Iterable[datetime], timezone_name: str
) -> tuple[int, datetime | None, str | None]:
    """
    Compute a consecutive-day streak given a list of UTC datetimes and the user's timezone.

    Returns (streak_count, last_studied_at_utc, last_studied_at_local_iso).
    """
    try:
        tz = pytz.timezone(timezone_name)
    except Exception:
        tz = pytz.utc

    # Convert to local dates
    local_dates = set()
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

    # Count consecutive days ending at the most recent local date present
    most_recent_local = max(local_dates)
    streak = 0
    cursor = most_recent_local
    while cursor in local_dates:
        streak += 1
        cursor = cursor - timedelta(days=1)

    last_studied_local_iso = None
    if last_dt is not None:
        # Use the tz we already resolved above (falls back to UTC on error)
        try:
            last_studied_local_iso = last_dt.astimezone(tz).isoformat()
        except Exception:
            # As a final fallback produce UTC string
            last_studied_local_iso = last_dt.astimezone(pytz.utc).isoformat()

    return streak, last_dt, last_studied_local_iso


def _resolve_local_time(dt: datetime | None, timezone_name: str) -> str | None:
    """Return localized ISO string for `dt` in `timezone_name`, falling back to UTC on error.

    Returns None when `dt` is falsy.
    """
    if not dt:
        return None
    try:
        return cast(str, to_local_time(dt, timezone_name))
    except Exception:
        try:
            return cast(str, to_local_time(dt, "UTC"))
        except Exception:
            return None


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


async def get_user_progress(db: AsyncSession, user: User) -> dict[str, Any]:
    """Get aggregate progress for a user."""
    total_answered, correct_answers, last_studied_dt = await _fetch_progress_aggregates(db, user)

    accuracy = compute_accuracy(total_answered, correct_answers)
    last_studied_at_local = _resolve_local_time(last_studied_dt, user.timezone)

    return {
        "total_answered": total_answered,
        "correct_answers": correct_answers,
        "accuracy": accuracy,
        "last_studied_at": last_studied_dt,
        "last_studied_at_local": last_studied_at_local,
    }


async def get_deck_progress(db: AsyncSession, user: User, deck_id: str) -> dict[str, Any]:
    """Get progress for a specific deck for a user."""
    total_answered, correct_answers, last_studied_dt = await _fetch_progress_aggregates(
        db, user, deck_id=deck_id
    )

    accuracy = compute_accuracy(total_answered, correct_answers)
    last_studied_at_local = _resolve_local_time(last_studied_dt, user.timezone)

    return {
        "deck_id": deck_id,
        "total_answered": total_answered,
        "correct_answers": correct_answers,
        "accuracy": accuracy,
        "last_studied_at": last_studied_dt,
        "last_studied_at_local": last_studied_at_local,
    }


async def get_user_streak(db: AsyncSession, user: User) -> dict[str, Any]:
    stmt = (
        select(SessionCard.answered_at)
        .join(Session, Session.id == SessionCard.session_id)
        .where(Session.user_id == user.id)
        .where(SessionCard.answered)
    )
    result = await db.execute(stmt)
    datetimes = [row[0] for row in result.fetchall() if row[0] is not None]

    streak, last_dt, last_local_iso = compute_streak_from_datetimes(datetimes, user.timezone)
    return {"streak": streak, "last_studied_at": last_dt, "last_studied_at_local": last_local_iso}
