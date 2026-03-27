from datetime import UTC, datetime

from mnemo.services.progress import compute_accuracy, compute_streak_from_datetimes


def test_compute_accuracy_zero() -> None:
    assert compute_accuracy(0, 0) == 0.0
    assert compute_accuracy(10, 0) == 0.0


def test_compute_accuracy_normal() -> None:
    assert compute_accuracy(4, 3) == 75.0
    assert compute_accuracy(3, 2) == 66.67


def test_streak_rollover_local_midnight() -> None:
    # User in UTC+3 (Europe/Moscow). Two UTC datetimes that map to consecutive
    # local dates: UTC 2026-03-21T20:30 -> local 2026-03-21T23:30
    # UTC 2026-03-21T21:30 -> local 2026-03-22T00:30
    dt_prev = datetime(2026, 3, 21, 20, 30, tzinfo=UTC)
    dt_recent = datetime(2026, 3, 21, 21, 30, tzinfo=UTC)
    # Inject now = dt_recent so local "today" = 2026-03-22 in Moscow
    streak, last_dt, last_local = compute_streak_from_datetimes(
        [dt_prev, dt_recent], "Europe/Moscow", now=dt_recent
    )

    assert streak == 2
    assert last_dt == dt_recent
    assert last_local is not None
    assert last_local.startswith("2026-03-22")


def test_compute_accuracy_rounding() -> None:
    # 1/3 -> 33.333... -> rounded to 33.33
    assert compute_accuracy(3, 1) == 33.33
    # 4/6 -> 66.666... -> rounded to 66.67
    assert compute_accuracy(6, 4) == 66.67


def test_streak_single_day_and_empty() -> None:
    dt = datetime(2026, 3, 22, 12, 0, tzinfo=UTC)
    # Inject now so local "today" = 2026-03-22 in Moscow
    streak, last_dt, last_local = compute_streak_from_datetimes([dt], "Europe/Moscow", now=dt)
    assert streak == 1
    assert last_dt == dt
    assert last_local is not None
    assert last_local.startswith("2026-03-22")

    streak_empty, last_dt_empty, last_local_empty = compute_streak_from_datetimes(
        [], "Europe/Moscow", now=dt
    )
    assert streak_empty == 0
    assert last_dt_empty is None
    assert last_local_empty is None


def test_streak_non_consecutive_days() -> None:
    # Two UTC datetimes mapping to non-consecutive local dates -> streak 1
    dt1 = datetime(2026, 3, 20, 12, 0, tzinfo=UTC)
    dt2 = datetime(2026, 3, 22, 12, 0, tzinfo=UTC)
    # Inject now so local "today" = 2026-03-22 in Moscow
    streak, last_dt, last_local = compute_streak_from_datetimes(
        [dt1, dt2], "Europe/Moscow", now=dt2
    )
    assert streak == 1
    assert last_dt == dt2


def test_streak_with_naive_datetimes_and_negative_offset() -> None:
    # Naive datetimes should be treated as UTC
    dt_prev = datetime(2026, 3, 21, 20, 30)
    dt_recent = datetime(2026, 3, 21, 21, 30)
    # Inject now (aware) so local "today" = 2026-03-22 in Moscow
    now_moscow = datetime(2026, 3, 21, 21, 30, tzinfo=UTC)
    streak, last_dt, last_local = compute_streak_from_datetimes(
        [dt_prev, dt_recent], "Europe/Moscow", now=now_moscow
    )
    assert streak == 2
    assert last_local is not None
    assert last_local.startswith("2026-03-22")

    # Negative offset example (America/New_York UTC-4)
    dt_prev = datetime(2026, 3, 22, 3, 30, tzinfo=UTC)
    dt_recent = datetime(2026, 3, 22, 4, 30, tzinfo=UTC)
    # Inject now so local "today" = 2026-03-22 in New York
    streak_ny, last_dt_ny, last_local_ny = compute_streak_from_datetimes(
        [dt_prev, dt_recent], "America/New_York", now=dt_recent
    )
    assert streak_ny == 2
    assert last_local_ny is not None
    assert last_local_ny.startswith("2026-03-22")


def test_invalid_timezone_fallback_for_streak() -> None:
    # Invalid timezone name should be handled and fall back to UTC
    dt_prev = datetime(2026, 3, 21, 20, 30, tzinfo=UTC)
    dt_recent = datetime(2026, 3, 21, 21, 30, tzinfo=UTC)
    # Inject now = dt_recent so local "today" = 2026-03-21 in UTC (fallback)
    streak, last_dt, last_local = compute_streak_from_datetimes(
        [dt_prev, dt_recent], "Invalid/Zone", now=dt_recent
    )
    # Fallback uses UTC mapping -> both datetimes map to 2026-03-21 in UTC
    assert streak == 1
    assert last_local is not None
    assert last_local.startswith("2026-03-21")


def test_streak_broken_when_gap_greater_than_one_day() -> None:
    # Last study was 2026-03-20; "today" is 2026-03-22 -> gap of 2 days -> streak 0
    dt = datetime(2026, 3, 20, 12, 0, tzinfo=UTC)
    now = datetime(2026, 3, 22, 12, 0, tzinfo=UTC)
    streak, last_dt, last_local = compute_streak_from_datetimes([dt], "UTC", now=now)
    assert streak == 0
    assert last_dt == dt


def test_streak_still_active_when_studied_yesterday() -> None:
    # Last study was yesterday local time; today has no study yet -> streak preserved
    dt = datetime(2026, 3, 21, 12, 0, tzinfo=UTC)
    # now is the following day in UTC -> gap = 1 -> streak still active
    now = datetime(2026, 3, 22, 6, 0, tzinfo=UTC)
    streak, last_dt, last_local = compute_streak_from_datetimes([dt], "UTC", now=now)
    assert streak == 1
    assert last_dt == dt
