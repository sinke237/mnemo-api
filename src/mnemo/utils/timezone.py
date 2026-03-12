"""
Timezone resolution utilities.
Maps ISO 3166-1 country codes to IANA timezones per spec.
"""

import pytz

# Mapping of ISO 3166-1 alpha-2 country codes to primary IANA timezone
# For countries with multiple timezones, this provides the most populous/common one
COUNTRY_TO_TIMEZONE: dict[str, str] = {
    # Africa
    "CM": "Africa/Douala",  # Cameroon
    "NG": "Africa/Lagos",  # Nigeria
    "KE": "Africa/Nairobi",  # Kenya
    "ZA": "Africa/Johannesburg",  # South Africa
    "EG": "Africa/Cairo",  # Egypt
    "GH": "Africa/Accra",  # Ghana
    "ET": "Africa/Addis_Ababa",  # Ethiopia
    "TZ": "Africa/Dar_es_Salaam",  # Tanzania
    "UG": "Africa/Kampala",  # Uganda
    "DZ": "Africa/Algiers",  # Algeria
    "MA": "Africa/Casablanca",  # Morocco
    "AO": "Africa/Luanda",  # Angola
    "SD": "Africa/Khartoum",  # Sudan
    "SN": "Africa/Dakar",  # Senegal
    "CI": "Africa/Abidjan",  # Côte d'Ivoire
    "RW": "Africa/Kigali",  # Rwanda
    # Europe
    "GB": "Europe/London",  # United Kingdom
    "FR": "Europe/Paris",  # France
    "DE": "Europe/Berlin",  # Germany
    "IT": "Europe/Rome",  # Italy
    "ES": "Europe/Madrid",  # Spain
    "PL": "Europe/Warsaw",  # Poland
    "NL": "Europe/Amsterdam",  # Netherlands
    "BE": "Europe/Brussels",  # Belgium
    "SE": "Europe/Stockholm",  # Sweden
    "CH": "Europe/Zurich",  # Switzerland
    "AT": "Europe/Vienna",  # Austria
    "PT": "Europe/Lisbon",  # Portugal
    "GR": "Europe/Athens",  # Greece
    "CZ": "Europe/Prague",  # Czech Republic
    "RO": "Europe/Bucharest",  # Romania
    "HU": "Europe/Budapest",  # Hungary
    "IE": "Europe/Dublin",  # Ireland
    "DK": "Europe/Copenhagen",  # Denmark
    "FI": "Europe/Helsinki",  # Finland
    "NO": "Europe/Oslo",  # Norway
    # Americas
    "US": "America/New_York",  # United States (Eastern - most populous)
    "CA": "America/Toronto",  # Canada (Eastern - most populous)
    "MX": "America/Mexico_City",  # Mexico
    "BR": "America/Sao_Paulo",  # Brazil (most populous)
    "AR": "America/Argentina/Buenos_Aires",  # Argentina
    "CO": "America/Bogota",  # Colombia
    "PE": "America/Lima",  # Peru
    "VE": "America/Caracas",  # Venezuela
    "CL": "America/Santiago",  # Chile
    "EC": "America/Guayaquil",  # Ecuador
    "CU": "America/Havana",  # Cuba
    "DO": "America/Santo_Domingo",  # Dominican Republic
    "JM": "America/Jamaica",  # Jamaica
    # Asia
    "CN": "Asia/Shanghai",  # China
    "IN": "Asia/Kolkata",  # India
    "JP": "Asia/Tokyo",  # Japan
    "KR": "Asia/Seoul",  # South Korea
    "ID": "Asia/Jakarta",  # Indonesia (Western - most populous)
    "TH": "Asia/Bangkok",  # Thailand
    "VN": "Asia/Ho_Chi_Minh",  # Vietnam
    "PH": "Asia/Manila",  # Philippines
    "MY": "Asia/Kuala_Lumpur",  # Malaysia
    "SG": "Asia/Singapore",  # Singapore
    "BD": "Asia/Dhaka",  # Bangladesh
    "PK": "Asia/Karachi",  # Pakistan
    "SA": "Asia/Riyadh",  # Saudi Arabia
    "AE": "Asia/Dubai",  # United Arab Emirates
    "IL": "Asia/Jerusalem",  # Israel
    "IQ": "Asia/Baghdad",  # Iraq
    "IR": "Asia/Tehran",  # Iran
    "TR": "Europe/Istanbul",  # Turkey
    # Oceania
    "AU": "Australia/Sydney",  # Australia (Eastern - most populous)
    "NZ": "Pacific/Auckland",  # New Zealand
    "PG": "Pacific/Port_Moresby",  # Papua New Guinea
    "FJ": "Pacific/Fiji",  # Fiji
}

# Countries with multiple timezones require secondary selection
# These will need an additional UI step to select specific timezone
MULTI_TIMEZONE_COUNTRIES: dict[str, list[str]] = {
    "US": [
        "America/New_York",  # Eastern
        "America/Chicago",  # Central
        "America/Denver",  # Mountain
        "America/Los_Angeles",  # Pacific
        "America/Anchorage",  # Alaska
        "Pacific/Honolulu",  # Hawaii
    ],
    "CA": [
        "America/St_Johns",  # Newfoundland
        "America/Halifax",  # Atlantic
        "America/Toronto",  # Eastern
        "America/Winnipeg",  # Central
        "America/Edmonton",  # Mountain
        "America/Vancouver",  # Pacific
    ],
    "BR": [
        "America/Noronha",  # Fernando de Noronha
        "America/Sao_Paulo",  # Brasília
        "America/Manaus",  # Amazon
        "America/Rio_Branco",  # Acre
    ],
    "AU": [
        "Australia/Perth",  # Western
        "Australia/Darwin",  # Central
        "Australia/Brisbane",  # Eastern (Queensland)
        "Australia/Sydney",  # Eastern (NSW/Victoria/Tasmania)
        "Australia/Adelaide",  # Central (South Australia)
    ],
    "RU": [
        "Europe/Kaliningrad",
        "Europe/Moscow",
        "Europe/Samara",
        "Asia/Yekaterinburg",
        "Asia/Omsk",
        "Asia/Krasnoyarsk",
        "Asia/Irkutsk",
        "Asia/Yakutsk",
        "Asia/Vladivostok",
        "Asia/Magadan",
        "Asia/Kamchatka",
    ],
    "MX": [
        "America/Tijuana",  # Northwest
        "America/Hermosillo",  # Sonora
        "America/Chihuahua",  # Chihuahua/Sinaloa
        "America/Mexico_City",  # Central
        "America/Cancun",  # Southeast
    ],
}


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
    return COUNTRY_TO_TIMEZONE.get(country_code.upper())


def country_has_multiple_timezones(country_code: str) -> bool:
    """
    Check if a country has multiple timezones requiring user selection.

    Args:
        country_code: ISO 3166-1 alpha-2 country code

    Returns:
        True if country has multiple timezones, False otherwise
    """
    return country_code.upper() in MULTI_TIMEZONE_COUNTRIES


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
    if code in MULTI_TIMEZONE_COUNTRIES:
        return MULTI_TIMEZONE_COUNTRIES[code]

    single_tz = get_timezone_for_country(code)
    return [single_tz] if single_tz else []


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
    return sorted(COUNTRY_TO_TIMEZONE.keys())
