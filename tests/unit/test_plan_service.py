"""
Unit tests for the study plan service (plan generation and date labels).
Covers:
- Schedule generation logic
- Local date labels reflect user's timezone (FR-07.2)
- Plan generation with DeckNotFoundError on bad deck
- get_active_plan returns most-recent plan or raises PlanNotFoundError
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from mnemo.core.exceptions import DeckNotFoundError, PlanNotFoundError
from mnemo.models.deck import Deck
from mnemo.models.study_plan import StudyPlan
from mnemo.models.user import User
from mnemo.services.plan import (
    _today_in_timezone,
    create_plan,
    generate_schedule,
    get_active_plan,
)

# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_user(timezone: str = "UTC") -> User:
    return User(id="usr_abc123", country="CM", timezone=timezone)


def _make_deck(card_count: int = 50, name: str = "Test Deck") -> Deck:
    return Deck(
        id="dck_xyz789",
        user_id="usr_abc123",
        name=name,
        card_count=card_count,
    )


def _make_db(deck: Deck | None = None, plan: StudyPlan | None = None) -> AsyncMock:
    db = AsyncMock()

    deck_result = MagicMock()
    deck_result.scalar_one_or_none.return_value = deck

    plan_result = MagicMock()
    plan_result.scalar_one_or_none.return_value = plan

    db.execute.side_effect = [deck_result, plan_result]
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    return db


# ── generate_schedule unit tests ──────────────────────────────────────────────


def test_schedule_length_matches_days() -> None:
    start = date(2025, 11, 1)
    schedule = generate_schedule(
        total_cards=50,
        days=7,
        daily_target=8,
        max_cards_per_day=15,
        start_date=start,
        deck_name="Finance",
    )
    assert len(schedule) == 7


def test_schedule_day_numbers_are_sequential() -> None:
    start = date(2025, 11, 1)
    schedule = generate_schedule(
        total_cards=56,
        days=7,
        daily_target=8,
        max_cards_per_day=20,
        start_date=start,
        deck_name="x",
    )
    for i, entry in enumerate(schedule, start=1):
        assert entry["day"] == i


def test_schedule_dates_are_consecutive_local_dates() -> None:
    """Each schedule date must be exactly one calendar day after the previous."""
    start = date(2025, 11, 2)
    schedule = generate_schedule(
        total_cards=30,
        days=5,
        daily_target=6,
        max_cards_per_day=10,
        start_date=start,
        deck_name="Biology",
    )
    for i, entry in enumerate(schedule):
        expected = (start + timedelta(days=i)).isoformat()
        assert entry["date"] == expected


def test_schedule_day1_has_no_reviews() -> None:
    """Day 1 must consist entirely of new cards (zero review overhead)."""
    start = date(2026, 1, 1)
    schedule = generate_schedule(
        total_cards=20,
        days=5,
        daily_target=4,
        max_cards_per_day=10,
        start_date=start,
        deck_name="Math",
    )
    assert schedule[0]["cards_to_study"] == 4  # exactly daily_target, no reviews


def test_schedule_reviews_increase_from_day2() -> None:
    """cards_to_study on day 2 should exceed daily_target due to review load."""
    start = date(2026, 3, 21)
    schedule = generate_schedule(
        total_cards=100,
        days=5,
        daily_target=20,
        max_cards_per_day=50,
        start_date=start,
        deck_name="History",
    )
    # Day 1: 20 new, 0 reviews → 20
    # Day 2: 20 new + int(20 * 0.25) = 20 + 5 = 25
    assert schedule[0]["cards_to_study"] == 20
    assert schedule[1]["cards_to_study"] == 25


def test_schedule_capped_by_max_cards_per_day() -> None:
    """cards_to_study must not exceed max_cards_per_day at any point."""
    start = date(2026, 3, 21)
    max_daily = 10
    schedule = generate_schedule(
        total_cards=100,
        days=10,
        daily_target=10,
        max_cards_per_day=max_daily,
        start_date=start,
        deck_name="Physics",
    )
    for entry in schedule:
        assert entry["cards_to_study"] <= max_daily


def test_schedule_focus_day1_contains_deck_name() -> None:
    start = date(2026, 3, 21)
    schedule = generate_schedule(
        total_cards=10,
        days=3,
        daily_target=4,
        max_cards_per_day=8,
        start_date=start,
        deck_name="PSD2",
    )
    assert "PSD2" in schedule[0]["focus"]


def test_schedule_focus_day2_mentions_reviews() -> None:
    start = date(2026, 3, 21)
    schedule = generate_schedule(
        total_cards=30,
        days=4,
        daily_target=8,
        max_cards_per_day=20,
        start_date=start,
        deck_name="Auth",
    )
    assert "review" in schedule[1]["focus"].lower()


def test_schedule_consolidation_phase_when_new_cards_exhausted() -> None:
    """Once all new cards are introduced, focus should indicate review/consolidation."""
    start = date(2026, 3, 21)
    # 5 cards, daily_target=5 → after day 1, no new cards remain
    schedule = generate_schedule(
        total_cards=5,
        days=3,
        daily_target=5,
        max_cards_per_day=10,
        start_date=start,
        deck_name="Vocab",
    )
    # Day 2 onward: no new cards
    assert (
        "review" in schedule[1]["focus"].lower() or "consolidation" in schedule[1]["focus"].lower()
    )
    assert (
        "review" in schedule[2]["focus"].lower() or "consolidation" in schedule[2]["focus"].lower()
    )


# ── Timezone date label tests (FR-07.2) ───────────────────────────────────────


def test_today_in_timezone_utc_plus3() -> None:
    """A datetime at 23:00 UTC should appear as next day in UTC+3."""
    # 2025-11-01T23:00:00 UTC → 2025-11-02T02:00:00 Africa/Nairobi (UTC+3)
    utc_midnight = datetime(2025, 11, 1, 23, 0, 0, tzinfo=UTC)
    local_date = _today_in_timezone("Africa/Nairobi", now=utc_midnight)
    assert local_date == date(2025, 11, 2)


def test_today_in_timezone_utc_minus5() -> None:
    """A datetime at 01:00 UTC should appear as previous day in UTC-5."""
    # 2025-11-02T01:00:00 UTC → 2025-11-01T20:00:00 America/New_York (UTC-5 in Nov)
    utc_early = datetime(2025, 11, 2, 1, 0, 0, tzinfo=UTC)
    local_date = _today_in_timezone("America/New_York", now=utc_early)
    assert local_date == date(2025, 11, 1)


def test_schedule_start_date_reflects_user_timezone() -> None:
    """
    When a plan is generated, the first schedule date must be today in the
    user's local timezone, not today in UTC.

    Scenario: 2025-11-01T23:00 UTC, user in Africa/Nairobi (UTC+3) → local
    date is 2025-11-02, so schedule[0]["date"] == "2025-11-02".
    """
    utc_now = datetime(2025, 11, 1, 23, 0, 0, tzinfo=UTC)
    local_start = _today_in_timezone("Africa/Nairobi", now=utc_now)
    schedule = generate_schedule(
        total_cards=7,
        days=3,
        daily_target=3,
        max_cards_per_day=5,
        start_date=local_start,
        deck_name="Deck",
    )
    assert schedule[0]["date"] == "2025-11-02"
    assert schedule[1]["date"] == "2025-11-03"
    assert schedule[2]["date"] == "2025-11-04"


def test_schedule_start_date_utc_minus_timezone() -> None:
    """User in UTC-5: 2025-11-02T01:00 UTC → local date 2025-11-01."""
    utc_now = datetime(2025, 11, 2, 1, 0, 0, tzinfo=UTC)
    local_start = _today_in_timezone("America/New_York", now=utc_now)
    schedule = generate_schedule(
        total_cards=4,
        days=2,
        daily_target=2,
        max_cards_per_day=5,
        start_date=local_start,
        deck_name="Deck",
    )
    assert schedule[0]["date"] == "2025-11-01"
    assert schedule[1]["date"] == "2025-11-02"


# ── create_plan service tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_plan_raises_deck_not_found() -> None:
    """create_plan must raise DeckNotFoundError when deck does not exist."""
    db = _make_db(deck=None)
    user = _make_user("UTC")

    with pytest.raises(DeckNotFoundError):
        await create_plan(
            db=db, user=user, deck_id="dck_missing", goal=None, days=7, daily_minutes=30
        )


@pytest.mark.asyncio
async def test_create_plan_happy_path() -> None:
    """create_plan returns a StudyPlan with correctly computed fields."""
    deck = _make_deck(card_count=28, name="OAuth 2.0")
    db = _make_db(deck=deck)
    user = _make_user("UTC")

    # Override refresh to populate the plan id so assertions are predictable
    refreshed: list[StudyPlan] = []

    async def _fake_refresh(obj: StudyPlan) -> None:
        obj.created_at = datetime(2026, 3, 21, 12, 0, 0, tzinfo=UTC)
        refreshed.append(obj)

    db.refresh = _fake_refresh

    now = datetime(2026, 3, 21, 12, 0, 0, tzinfo=UTC)
    plan = await create_plan(
        db=db,
        user=user,
        deck_id="dck_xyz789",
        goal="Pass OAuth certification",
        days=7,
        daily_minutes=30,
        now=now,
    )

    assert plan.user_id == user.id
    assert plan.deck_id == "dck_xyz789"
    assert plan.goal == "Pass OAuth certification"
    assert plan.days == 7
    assert plan.daily_target >= 1
    assert isinstance(plan.schedule, list)
    assert len(plan.schedule) == 7
    # All schedule dates must be YYYY-MM-DD strings
    for entry in plan.schedule:
        assert isinstance(entry, dict)
        assert len(str(entry["date"])) == 10
        assert str(entry["date"])[4] == "-" and str(entry["date"])[7] == "-"
        assert int(entry["cards_to_study"]) >= 1


@pytest.mark.asyncio
async def test_create_plan_daily_target_uses_time_budget() -> None:
    """When daily_minutes is very small the daily_target is capped by time budget."""
    deck = _make_deck(card_count=100)
    db = _make_db(deck=deck)
    user = _make_user("UTC")

    async def _fake_refresh(obj: StudyPlan) -> None:
        obj.created_at = datetime(2026, 3, 21, 0, 0, 0, tzinfo=UTC)

    db.refresh = _fake_refresh

    # 2 minutes/day → max 1 card/day (2 min // 2 min-per-card = 1)
    now = datetime(2026, 3, 21, 0, 0, 0, tzinfo=UTC)
    plan = await create_plan(
        db=db, user=user, deck_id="dck_xyz789", goal=None, days=14, daily_minutes=2, now=now
    )
    assert plan.daily_target == 1


@pytest.mark.asyncio
async def test_create_plan_empty_deck() -> None:
    """An empty deck (card_count=0) should produce a valid plan with 1 card target."""
    deck = _make_deck(card_count=0, name="Empty Deck")
    db = _make_db(deck=deck)
    user = _make_user("UTC")

    async def _fake_refresh(obj: StudyPlan) -> None:
        obj.created_at = datetime(2026, 3, 21, 0, 0, 0, tzinfo=UTC)

    db.refresh = _fake_refresh

    now = datetime(2026, 3, 21, 0, 0, 0, tzinfo=UTC)
    plan = await create_plan(
        db=db, user=user, deck_id="dck_xyz789", goal=None, days=5, daily_minutes=30, now=now
    )
    assert plan.daily_target >= 1
    assert isinstance(plan.schedule, list)
    assert len(plan.schedule) == 5


# ── get_active_plan tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_active_plan_raises_when_none() -> None:
    """get_active_plan must raise PlanNotFoundError when no plan exists."""
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result

    with pytest.raises(PlanNotFoundError):
        await get_active_plan(db, "usr_abc123")


@pytest.mark.asyncio
async def test_get_active_plan_returns_plan() -> None:
    """get_active_plan returns the plan when one exists."""
    plan = StudyPlan(
        id="pln_test",
        user_id="usr_abc123",
        deck_id="dck_xyz789",
        goal=None,
        days=7,
        daily_target=5,
        daily_minutes=30,
        schedule=[],
    )
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = plan
    db.execute.return_value = result

    fetched = await get_active_plan(db, "usr_abc123")
    assert fetched.id == "pln_test"
