"""
Tests for countries endpoint.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from mnemo.main import app


@pytest.mark.asyncio
async def test_get_countries() -> None:
    """Test GET /v1/countries returns list of supported countries."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/v1/countries")

    assert response.status_code == 200
    data = response.json()

    assert "countries" in data
    assert "total" in data
    assert data["total"] > 0
    assert len(data["countries"]) == data["total"]

    # Verify structure of first country
    first_country = data["countries"][0]
    assert "code" in first_country
    assert "primary_timezone" in first_country
    assert "has_multiple_timezones" in first_country
    assert "all_timezones" in first_country
    assert isinstance(first_country["all_timezones"], list)


@pytest.mark.asyncio
async def test_get_countries_includes_cameroon() -> None:
    """Test that Cameroon (CM) is in the list."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/v1/countries")

    data = response.json()
    countries = data["countries"]

    cm = next((c for c in countries if c["code"] == "CM"), None)
    assert cm is not None
    assert cm["primary_timezone"] == "Africa/Douala"
    assert cm["has_multiple_timezones"] is False
    assert cm["all_timezones"] == ["Africa/Douala"]


@pytest.mark.asyncio
async def test_get_countries_includes_multi_timezone() -> None:
    """Test that multi-timezone countries are properly flagged."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/v1/countries")

    data = response.json()
    countries = data["countries"]

    us = next((c for c in countries if c["code"] == "US"), None)
    assert us is not None
    assert us["has_multiple_timezones"] is True
    assert len(us["all_timezones"]) > 1
    assert "America/New_York" in us["all_timezones"]
    assert "America/Los_Angeles" in us["all_timezones"]


@pytest.mark.asyncio
async def test_get_single_country() -> None:
    """Test GET /v1/countries/{code} returns specific country info."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/v1/countries/CM")

    assert response.status_code == 200
    data = response.json()

    assert data["code"] == "CM"
    assert data["primary_timezone"] == "Africa/Douala"
    assert data["has_multiple_timezones"] is False
    assert data["all_timezones"] == ["Africa/Douala"]


@pytest.mark.asyncio
async def test_get_single_country_case_insensitive() -> None:
    """Test country code lookup is case-insensitive."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/v1/countries/cm")  # lowercase

    assert response.status_code == 200
    data = response.json()
    assert data["code"] == "CM"  # Returns uppercase


@pytest.mark.asyncio
async def test_get_single_country_multi_timezone() -> None:
    """Test single country endpoint for multi-timezone country."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/v1/countries/US")

    assert response.status_code == 200
    data = response.json()

    assert data["code"] == "US"
    assert data["has_multiple_timezones"] is True
    assert len(data["all_timezones"]) == 6  # US has 6 timezones
    assert "America/New_York" in data["all_timezones"]


@pytest.mark.asyncio
async def test_get_single_country_not_found() -> None:
    """Test GET /v1/countries/{code} returns 404 for unsupported country."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/v1/countries/ZZ")  # Invalid code

    assert response.status_code == 404
    error_data = response.json()
    assert error_data["detail"]["error"]["code"] == "INVALID_COUNTRY_CODE"


@pytest.mark.asyncio
async def test_countries_endpoint_no_auth_required() -> None:
    """Test that countries endpoint does not require authentication."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # No X-API-Key or Authorization header
        response = await client.get("/v1/countries")

    assert response.status_code == 200  # Should succeed without auth
