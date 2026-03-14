"""
Timezone resolution utilities.
Maps ISO 3166-1 country codes to IANA timezones per spec.
"""

from __future__ import annotations

import pycountry
import pytz

# Some ISO codes are missing in pytz country_timezones (e.g., BV, HM).
# Provide a conservative fallback so we still expose the full ISO list.
COUNTRY_TIMEZONE_OVERRIDES: dict[str, list[str]] = {
    "BV": ["Etc/UTC"],  # Bouvet Island
    "HM": ["Etc/UTC"],  # Heard and McDonald Islands
}

# Primary timezone overrides for multi-timezone countries
# to ensure a stable "most common" primary selection.
PRIMARY_TIMEZONE_OVERRIDES: dict[str, str] = {
    "US": "America/New_York",
    "CA": "America/Toronto",
    "BR": "America/Sao_Paulo",
    "AU": "Australia/Sydney",
    "RU": "Europe/Moscow",
    "MX": "America/Mexico_City",
}


def _raw_timezones_for_country(code: str) -> list[str]:
    if code in COUNTRY_TIMEZONE_OVERRIDES:
        return list(COUNTRY_TIMEZONE_OVERRIDES[code])
    return list(pytz.country_timezones.get(code, []))


def get_timezone_for_country(country_code: str) -> str | None:
    """
    Get the primary IANA timezone for a country code.

    Args:
        country_code: ISO 3166-1 alpha-2 country code (e.g., 'CM', 'US', 'GB')

    Returns:
        IANA timezone string or None if country not found

    Examples:
        >>> get_timezone_for_country('CM')
        'Africa/Douala'
        >>> get_timezone_for_country('US')
        'America/New_York'
    """
    timezones = get_timezones_for_country(country_code)
    return timezones[0] if timezones else None


def country_has_multiple_timezones(country_code: str) -> bool:
    """
    Check if a country has multiple timezones requiring user selection.

    Args:
        country_code: ISO 3166-1 alpha-2 country code

    Returns:
        True if country has multiple timezones, False otherwise
    """
    return len(get_timezones_for_country(country_code)) > 1


def get_timezones_for_country(country_code: str) -> list[str]:
    """
    Get all timezones for a country. For multi-timezone countries,
    returns the full list. For single-timezone countries, returns
    a list with one element.

    Args:
        country_code: ISO 3166-1 alpha-2 country code

    Returns:
        List of IANA timezone strings
    """
    code = country_code.upper()
    timezones = _raw_timezones_for_country(code)
    if not timezones:
        return []

    primary = PRIMARY_TIMEZONE_OVERRIDES.get(code, timezones[0])
    if primary in timezones:
        return [primary] + [tz for tz in timezones if tz != primary]
    return list(timezones)


def validate_timezone(timezone: str) -> bool:
    """
    Validate that a timezone string is a valid IANA timezone.

    Args:
        timezone: IANA timezone string (e.g., 'Africa/Douala')

    Returns:
        True if valid, False otherwise
    """
    try:
        pytz.timezone(timezone)
        return True
    except pytz.exceptions.UnknownTimeZoneError:
        return False


def get_all_supported_countries() -> list[str]:
    """
    Get list of all supported country codes.

    Returns:
        List of ISO 3166-1 alpha-2 country codes
    """
    codes = [c.alpha_2 for c in pycountry.countries]
    return sorted(codes)
