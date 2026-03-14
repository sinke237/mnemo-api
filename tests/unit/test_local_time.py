"""
Unit tests for local time conversion utilities.
"""

from datetime import UTC, datetime

from mnemo.utils.local_time import to_local_time


def test_to_local_time_converts_utc_to_offset() -> None:
    utc_dt = datetime(2026, 3, 10, 8, 30, 0, tzinfo=UTC)
    local = to_local_time(utc_dt, "Africa/Douala")
    assert local.startswith("2026-03-10T09:30:00")
    assert local.endswith("+01:00")


def test_to_local_time_handles_naive_as_utc() -> None:
    naive = datetime(2026, 3, 10, 8, 30, 0)
    local = to_local_time(naive, "Africa/Douala")
    assert local.startswith("2026-03-10T09:30:00")
