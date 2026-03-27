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


def test_get_timezone_for_country_known_single() -> None:
    assert get_timezone_for_country("GB") == "Europe/London"


def test_get_timezone_for_country_cm_ng() -> None:
    assert get_timezone_for_country("CM") == "Africa/Douala"
    assert get_timezone_for_country("NG") == "Africa/Lagos"


def test_get_timezone_for_country_case_insensitive() -> None:
    result_upper = get_timezone_for_country("DE")
    result_lower = get_timezone_for_country("de")
    assert result_upper == result_lower
    assert result_upper is not None


def test_get_timezone_for_country_unknown_returns_none() -> None:
    assert get_timezone_for_country("ZZ") is None


def test_get_timezone_for_country_multi_tz_country_returns_primary() -> None:
    # Multi-timezone countries still return a stable primary
    result = get_timezone_for_country("US")
    assert result == "America/New_York"


# ── country_has_multiple_timezones ─────────────────────────────────────────────


def test_country_has_multiple_timezones_true() -> None:
    assert country_has_multiple_timezones("US") is True
    assert country_has_multiple_timezones("CA") is True
    assert country_has_multiple_timezones("RU") is True


def test_country_has_multiple_timezones_false() -> None:
    assert country_has_multiple_timezones("GB") is False
    assert country_has_multiple_timezones("CM") is False
    assert country_has_multiple_timezones("JP") is False


def test_country_has_multiple_timezones_case_insensitive() -> None:
    assert country_has_multiple_timezones("us") is True
    assert country_has_multiple_timezones("gb") is False


# ── get_timezones_for_country ──────────────────────────────────────────────────


def test_get_timezones_for_country_multi_tz() -> None:
    timezones = get_timezones_for_country("US")
    assert isinstance(timezones, list)
    assert len(timezones) > 1
    assert "America/New_York" in timezones


def test_get_timezones_for_country_single_tz() -> None:
    timezones = get_timezones_for_country("GB")
    assert isinstance(timezones, list)
    assert len(timezones) == 1
    assert timezones[0] == "Europe/London"


def test_get_timezones_for_country_ru_multi_tz() -> None:
    timezones = get_timezones_for_country("RU")
    assert isinstance(timezones, list)
    assert len(timezones) > 1
    assert "Europe/Moscow" in timezones


def test_get_timezones_for_country_unknown() -> None:
    timezones = get_timezones_for_country("ZZ")
    assert timezones == []


def test_get_timezones_for_country_case_insensitive() -> None:
    result_upper = get_timezones_for_country("US")
    result_lower = get_timezones_for_country("us")
    assert result_upper == result_lower


# ── validate_timezone ──────────────────────────────────────────────────────────


def test_validate_timezone_valid() -> None:
    assert validate_timezone("Europe/London") is True
    assert validate_timezone("America/New_York") is True
    assert validate_timezone("Asia/Tokyo") is True
    assert validate_timezone("Africa/Douala") is True


def test_validate_timezone_invalid() -> None:
    assert validate_timezone("Not/ATimezone") is False
    assert validate_timezone("random_string") is False
    assert validate_timezone("") is False


# ── get_all_supported_countries ────────────────────────────────────────────────


def test_get_all_supported_countries_returns_list() -> None:
    countries = get_all_supported_countries()
    assert isinstance(countries, list)
    assert len(countries) > 0


def test_get_all_supported_countries_sorted() -> None:
    countries = get_all_supported_countries()
    assert countries == sorted(countries)


def test_get_all_supported_countries_contains_common() -> None:
    countries = get_all_supported_countries()
    for code in ("GB", "DE", "JP", "FR", "IN"):
        assert code in countries
