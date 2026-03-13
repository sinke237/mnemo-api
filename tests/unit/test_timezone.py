"""
Unit tests for src/mnemo/utils/timezone.py.
All functions are pure — no mocks needed.
"""

from mnemo.utils.timezone import (
    country_has_multiple_timezones,
    get_all_supported_countries,
    get_timezone_for_country,
    get_timezones_for_country,
    validate_timezone,
)

# ── get_timezone_for_country ───────────────────────────────────────────────────


def test_get_timezone_for_country_known_single():
    assert get_timezone_for_country("GB") == "Europe/London"


def test_get_timezone_for_country_case_insensitive():
    result_upper = get_timezone_for_country("DE")
    result_lower = get_timezone_for_country("de")
    assert result_upper == result_lower
    assert result_upper is not None


def test_get_timezone_for_country_unknown_returns_none():
    assert get_timezone_for_country("ZZ") is None


def test_get_timezone_for_country_multi_tz_country_returns_primary():
    # US is in MULTI_TIMEZONE_COUNTRIES but also has a primary entry
    result = get_timezone_for_country("US")
    assert result is not None


# ── country_has_multiple_timezones ─────────────────────────────────────────────


def test_country_has_multiple_timezones_true():
    assert country_has_multiple_timezones("US") is True
    assert country_has_multiple_timezones("CA") is True
    assert country_has_multiple_timezones("RU") is True


def test_country_has_multiple_timezones_false():
    assert country_has_multiple_timezones("GB") is False
    assert country_has_multiple_timezones("DE") is False
    assert country_has_multiple_timezones("JP") is False


def test_country_has_multiple_timezones_case_insensitive():
    assert country_has_multiple_timezones("us") is True
    assert country_has_multiple_timezones("gb") is False


# ── get_timezones_for_country ──────────────────────────────────────────────────


def test_get_timezones_for_country_multi_tz():
    timezones = get_timezones_for_country("US")
    assert isinstance(timezones, list)
    assert len(timezones) > 1
    assert "America/New_York" in timezones


def test_get_timezones_for_country_single_tz():
    timezones = get_timezones_for_country("GB")
    assert isinstance(timezones, list)
    assert len(timezones) == 1
    assert timezones[0] == "Europe/London"


def test_get_timezones_for_country_unknown():
    timezones = get_timezones_for_country("ZZ")
    assert timezones == []


def test_get_timezones_for_country_case_insensitive():
    result_upper = get_timezones_for_country("US")
    result_lower = get_timezones_for_country("us")
    assert result_upper == result_lower


# ── validate_timezone ──────────────────────────────────────────────────────────


def test_validate_timezone_valid():
    assert validate_timezone("Europe/London") is True
    assert validate_timezone("America/New_York") is True
    assert validate_timezone("Asia/Tokyo") is True
    assert validate_timezone("Africa/Douala") is True


def test_validate_timezone_invalid():
    assert validate_timezone("Not/ATimezone") is False
    assert validate_timezone("random_string") is False
    assert validate_timezone("") is False


# ── get_all_supported_countries ────────────────────────────────────────────────


def test_get_all_supported_countries_returns_list():
    countries = get_all_supported_countries()
    assert isinstance(countries, list)
    assert len(countries) > 0


def test_get_all_supported_countries_sorted():
    countries = get_all_supported_countries()
    assert countries == sorted(countries)


def test_get_all_supported_countries_contains_common():
    countries = get_all_supported_countries()
    for code in ("GB", "DE", "JP", "FR", "IN"):
        assert code in countries
