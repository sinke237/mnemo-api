"""
Local time utilities.
Converts UTC timestamps to user-local ISO 8601 strings with offset.
"""

from __future__ import annotations

from datetime import UTC, datetime, tzinfo
from typing import cast

import pytz


def to_local_time(utc_dt: datetime, timezone_name: str) -> str:
    """
    Convert a datetime to a user's local time string.

    Args:
        utc_dt: Datetime (naive treated as UTC or timezone-aware).
        timezone_name: IANA timezone name (e.g., "Africa/Douala").

    Returns:
        ISO 8601 string with timezone offset (e.g., "2026-03-10T09:30:00+01:00").
    """
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=UTC)
    else:
        utc_dt = utc_dt.astimezone(UTC)

    tz = cast(tzinfo, pytz.timezone(timezone_name))
    local_dt: datetime = utc_dt.astimezone(tz)
    return local_dt.isoformat()
