"""
Countries routes.
Returns supported countries and timezone information.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from mnemo.core.constants import ErrorCode
from mnemo.schemas.error import ErrorResponse
from mnemo.utils.timezone import (
    country_has_multiple_timezones,
    get_all_supported_countries,
    get_timezone_for_country,
    get_timezones_for_country,
)

router = APIRouter(prefix="/countries", tags=["countries"])


class CountryInfo(BaseModel):
    """Country information with timezone details."""

    code: str = Field(..., description="ISO 3166-1 alpha-2 country code")
    primary_timezone: str = Field(..., description="Primary IANA timezone")
    has_multiple_timezones: bool = Field(..., description="Whether country has multiple timezones")
    all_timezones: list[str] = Field(..., description="All available timezones for this country")

    model_config = {
        "json_schema_extra": {
            "example": {
                "code": "US",
                "primary_timezone": "America/New_York",
                "has_multiple_timezones": True,
                "all_timezones": [
                    "America/New_York",
                    "America/Chicago",
                    "America/Denver",
                    "America/Los_Angeles",
                    "America/Anchorage",
                    "Pacific/Honolulu",
                ],
            }
        }
    }


class CountriesResponse(BaseModel):
    """List of supported countries."""

    countries: list[CountryInfo] = Field(..., description="Supported countries")
    total: int = Field(..., description="Total number of supported countries")

    model_config = {
        "json_schema_extra": {
            "example": {
                "countries": [
                    {
                        "code": "CM",
                        "primary_timezone": "Africa/Douala",
                        "has_multiple_timezones": False,
                        "all_timezones": ["Africa/Douala"],
                    },
                    {
                        "code": "US",
                        "primary_timezone": "America/New_York",
                        "has_multiple_timezones": True,
                        "all_timezones": [
                            "America/New_York",
                            "America/Chicago",
                            "America/Denver",
                            "America/Los_Angeles",
                            "America/Anchorage",
                            "Pacific/Honolulu",
                        ],
                    },
                ],
                "total": 60,
            }
        }
    }


@router.get(
    "",
    response_model=CountriesResponse,
    summary="Get supported countries",
    description=(
        "Returns the list of all supported countries with their timezone information. "
        "Use this endpoint to populate country selection dropdowns. "
        "For countries with multiple timezones, the user must select a specific timezone "
        "from the all_timezones list when creating their account."
    ),
)
async def get_countries() -> CountriesResponse:
    """
    Get list of supported countries with timezone information.

    Returns:
        CountriesResponse with all supported countries
    """
    country_codes = get_all_supported_countries()

    countries = []
    for code in country_codes:
        primary_tz = get_timezone_for_country(code)
        all_tzs = get_timezones_for_country(code)
        has_multiple = country_has_multiple_timezones(code)

        countries.append(
            CountryInfo(
                code=code,
                primary_timezone=primary_tz,
                has_multiple_timezones=has_multiple,
                all_timezones=all_tzs,
            )
        )

    return CountriesResponse(countries=countries, total=len(countries))


@router.get(
    "/{country_code}",
    response_model=CountryInfo,
    summary="Get country timezone information",
    description=(
        "Returns timezone information for a specific country. "
        "Use this to check if a country has multiple timezones "
        "and get the list of available timezones."
    ),
    responses={
        404: {"model": ErrorResponse, "description": "Country code not supported"},
    },
)
async def get_country(country_code: str) -> CountryInfo:
    """
    Get timezone information for a specific country.

    Args:
        country_code: ISO 3166-1 alpha-2 country code (e.g., 'US', 'CM')

    Returns:
        CountryInfo with timezone details

    Raises:
        HTTPException: 404 if country code is not supported
    """

    code = country_code.upper()

    if get_timezone_for_country(code) is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": ErrorCode.INVALID_COUNTRY_CODE.value,
                    "message": f"Country code not supported: {code}",
                    "status": 404,
                }
            },
        )

    primary_tz = get_timezone_for_country(code)
    all_tzs = get_timezones_for_country(code)
    has_multiple = country_has_multiple_timezones(code)

    return CountryInfo(
        code=code,
        primary_timezone=primary_tz,
        has_multiple_timezones=has_multiple,
        all_timezones=all_tzs,
    )
