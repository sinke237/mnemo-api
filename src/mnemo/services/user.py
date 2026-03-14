"""
User service.
Handles user CRUD operations and profile management.
Per spec section 11: User Profiles.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.core.exceptions import (
    InvalidCountryCodeError,
    InvalidTimezoneError,
    MissingTimezoneError,
    TimezoneNotAllowedError,
)
from mnemo.models.user import User
from mnemo.schemas.user import UserCreate, UserUpdate
from mnemo.utils.id_generator import generate_user_id
from mnemo.utils.timezone import (
    country_has_multiple_timezones,
    get_timezones_for_country,
    validate_timezone,
)


def normalize_and_precheck_timezone(timezone: str) -> str:
    """
    Normalize and pre-validate a timezone string.

    Raises InvalidTimezoneError for blank/whitespace or invalid IANA identifiers.
    """
    normalized = timezone.strip()
    if not normalized:
        raise InvalidTimezoneError("Timezone cannot be blank or whitespace-only")
    if not validate_timezone(normalized):
        raise InvalidTimezoneError(f"Invalid timezone: {normalized}")
    return normalized


async def create_user(db: AsyncSession, user_data: UserCreate) -> User:
    """
    Create a new user account.

    Per spec FR-07.1:
    - country is REQUIRED
    - timezone is derived from country if not provided
    - For multi-timezone countries, user must select specific timezone

    Args:
        db: Database session
        user_data: User creation data

    Returns:
        Created User record

    Raises:
        InvalidCountryCodeError: If country code is not supported
        InvalidTimezoneError: If timezone is invalid
        MissingTimezoneError: If timezone is missing for multi-timezone country
    """

    def resolve_timezone(user_data: UserCreate) -> str:
        """
        Resolve timezone and validate country for user creation.

        Args:
            user_data: User creation data

        Raises:
            InvalidCountryCodeError: If country code is not supported
            InvalidTimezoneError: If timezone is invalid or doesn't match country
            MissingTimezoneError: If timezone required but not provided
        """
        tz_list: list[str] = get_timezones_for_country(user_data.country)
        if not tz_list:
            raise InvalidCountryCodeError(f"Unsupported country code: {user_data.country}")

        if user_data.timezone is not None:
            normalized_timezone = normalize_and_precheck_timezone(user_data.timezone)
            if country_has_multiple_timezones(user_data.country):
                if normalized_timezone not in tz_list:
                    raise InvalidTimezoneError(
                        f"Country {user_data.country} requires one of {tz_list}; "
                        f"got {normalized_timezone}"
                    )
            else:
                if normalized_timezone != tz_list[0]:
                    raise InvalidTimezoneError(
                        f"Invalid timezone {normalized_timezone} for {user_data.country}"
                    )
            return normalized_timezone
        else:
            if country_has_multiple_timezones(user_data.country):
                raise MissingTimezoneError(
                    f"Country {user_data.country} has multiple timezones. "
                    "User must select specific timezone."
                )
            # Set timezone for single-timezone countries
            return tz_list[0]

    # Resolve timezone and validate country
    resolved_timezone = resolve_timezone(user_data)

    # Create user record
    user = User(
        id=generate_user_id(),
        display_name=user_data.display_name,
        country=user_data.country.upper(),
        locale=user_data.locale,
        timezone=resolved_timezone,
        education_level=user_data.education_level.value if user_data.education_level else None,
        preferred_language=user_data.preferred_language,
        daily_goal_cards=user_data.daily_goal_cards,
    )

    db.add(user)
    await db.flush()

    return user


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    """
    Retrieve a user by ID.

    Args:
        db: Database session
        user_id: User ID (usr_xxx)

    Returns:
        User record or None if not found
    """
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def update_user(db: AsyncSession, user_id: str, user_data: UserUpdate) -> User | None:
    """
    Update user profile fields.

    Note: country cannot be changed after creation (per spec).
    timezone can only be updated for multi-timezone countries.

    Args:
        db: Database session
        user_id: User ID (usr_xxx)
        user_data: Fields to update

    Returns:
        Updated User record or None if user not found

    Raises:
        InvalidTimezoneError: If timezone is invalid
        TimezoneNotAllowedError: If trying to change timezone for single-TZ country
    """
    user = await get_user_by_id(db, user_id)
    if user is None:
        return None

    # Update fields that are provided
    if user_data.display_name is not None:
        user.display_name = user_data.display_name

    if user_data.locale is not None:
        user.locale = user_data.locale

    if user_data.timezone is not None:
        # Only allow changing timezone for users in multi-timezone countries
        if not country_has_multiple_timezones(user.country):
            raise TimezoneNotAllowedError(
                f"Cannot change timezone for country {user.country}; "
                "use country-derived timezone"
            )

        normalized_timezone = normalize_and_precheck_timezone(user_data.timezone)

        allowed_tzs: list[str] = get_timezones_for_country(user.country)
        if not allowed_tzs:
            raise InvalidTimezoneError(
                f"No timezones configured for multi-timezone country {user.country}"
            )
        if normalized_timezone not in allowed_tzs:
            raise InvalidTimezoneError(
                f"Timezone {normalized_timezone} is not valid for country {user.country}"
            )

        user.timezone = normalized_timezone

    if user_data.education_level is not None:
        user.education_level = user_data.education_level.value

    if user_data.preferred_language is not None:
        user.preferred_language = user_data.preferred_language

    if user_data.daily_goal_cards is not None:
        user.daily_goal_cards = user_data.daily_goal_cards

    await db.flush()

    return user


async def delete_user(db: AsyncSession, user_id: str) -> bool:
    """
    Delete a user account.

    Args:
        db: Database session
        user_id: User ID (usr_xxx)

    Returns:
        True if user was deleted, False if not found
    """
    user = await get_user_by_id(db, user_id)
    if user is None:
        return False

    await db.delete(user)
    await db.flush()

    return True


async def user_exists(db: AsyncSession, user_id: str) -> bool:
    """
    Check if a user exists.

    Args:
        db: Database session
        user_id: User ID (usr_xxx)

    Returns:
        True if user exists, False otherwise
    """
    # Use a lightweight existence query to avoid loading the full user row.
    result = await db.execute(select(1).where(User.id == user_id).limit(1))
    return result.scalar_one_or_none() is not None
