from datetime import UTC, datetime

from mnemo.services.progress import compute_accuracy, compute_streak_from_datetimes


def test_compute_accuracy_zero():
    assert compute_accuracy(0, 0) == 0.0
    assert compute_accuracy(10, 0) == 0.0


def test_compute_accuracy_normal():
    assert compute_accuracy(4, 3) == 75.0
    assert compute_accuracy(3, 2) == 66.67


def test_streak_rollover_local_midnight():
    # User in UTC+3 (Europe/Moscow). Two UTC datetimes that map to consecutive
    # local dates: UTC 2026-03-21T20:30 -> local 2026-03-21T23:30
    # UTC 2026-03-21T21:30 -> local 2026-03-22T00:30
    dt_prev = datetime(2026, 3, 21, 20, 30, tzinfo=UTC)
    dt_recent = datetime(2026, 3, 21, 21, 30, tzinfo=UTC)

    streak, last_dt, last_local = compute_streak_from_datetimes(
        [dt_prev, dt_recent], "Europe/Moscow"
    )

    assert streak == 2
    assert last_dt == dt_recent
    assert last_local.startswith("2026-03-22")


def test_compute_accuracy_rounding():
    # 1/3 -> 33.333... -> rounded to 33.33
    assert compute_accuracy(3, 1) == 33.33
    # 4/6 -> 66.666... -> rounded to 66.67
    assert compute_accuracy(6, 4) == 66.67


def test_streak_single_day_and_empty():
    dt = datetime(2026, 3, 22, 12, 0, tzinfo=UTC)
    streak, last_dt, last_local = compute_streak_from_datetimes([dt], "Europe/Moscow")
    assert streak == 1
    assert last_dt == dt
    assert last_local.startswith("2026-03-22")

    streak_empty, last_dt_empty, last_local_empty = compute_streak_from_datetimes(
        [], "Europe/Moscow"
    )
    assert streak_empty == 0
    assert last_dt_empty is None
    assert last_local_empty is None


def test_streak_non_consecutive_days():
    # Two UTC datetimes mapping to non-consecutive local dates -> streak 1
    dt1 = datetime(2026, 3, 20, 12, 0, tzinfo=UTC)
    dt2 = datetime(2026, 3, 22, 12, 0, tzinfo=UTC)
    streak, last_dt, last_local = compute_streak_from_datetimes([dt1, dt2], "Europe/Moscow")
    assert streak == 1
    assert last_dt == dt2


def test_streak_with_naive_datetimes_and_negative_offset():
    # Naive datetimes should be treated as UTC
    dt_prev = datetime(2026, 3, 21, 20, 30)
    dt_recent = datetime(2026, 3, 21, 21, 30)
    streak, last_dt, last_local = compute_streak_from_datetimes(
        [dt_prev, dt_recent], "Europe/Moscow"
    )
    assert streak == 2
    assert last_local.startswith("2026-03-22")

    # Negative offset example (America/New_York UTC-4)
    dt_prev = datetime(2026, 3, 22, 3, 30, tzinfo=UTC)
    dt_recent = datetime(2026, 3, 22, 4, 30, tzinfo=UTC)
    streak_ny, last_dt_ny, last_local_ny = compute_streak_from_datetimes(
        [dt_prev, dt_recent], "America/New_York"
    )
    assert streak_ny == 2
    assert last_local_ny.startswith("2026-03-22")


def test_invalid_timezone_fallback_for_streak():
    # Invalid timezone name should be handled and fall back to UTC
    dt_prev = datetime(2026, 3, 21, 20, 30, tzinfo=UTC)
    dt_recent = datetime(2026, 3, 21, 21, 30, tzinfo=UTC)
    streak, last_dt, last_local = compute_streak_from_datetimes(
        [dt_prev, dt_recent], "Invalid/Zone"
    )
    # Fallback uses UTC mapping -> both datetimes map to 2026-03-21 in UTC
    assert streak == 1
    assert last_local is not None
    assert last_local.startswith("2026-03-21")
