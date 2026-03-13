"""
User service.
Handles user CRUD operations and profile management.
Per spec section 11: User Profiles.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.models.user import User
from mnemo.schemas.user import UserCreate, UserUpdate
from mnemo.utils.id_generator import generate_user_id
from mnemo.utils.timezone import (
    country_has_multiple_timezones,
    get_timezones_for_country,
    validate_timezone,
)


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
        ValueError: If country is invalid or timezone is missing for multi-timezone country
    """

    def validate_timezone_and_country(user_data: UserCreate) -> None:
        """
        Validate timezone and country for user creation.

        Args:
            user_data: User creation data

        Returns:
            None
        """
        if user_data.timezone is not None:
            user_data.timezone = user_data.timezone.strip()
            if not user_data.timezone:
                raise ValueError("Timezone cannot be blank or whitespace-only.")
            if not validate_timezone(user_data.timezone):
                raise ValueError(f"Invalid timezone: {user_data.timezone}")
            tz_list = get_timezones_for_country(user_data.country)
            if not tz_list:
                raise ValueError(f"Unsupported country code: {user_data.country}")
            if country_has_multiple_timezones(user_data.country):
                if user_data.timezone not in tz_list:
                    raise ValueError(
                        f"Country {user_data.country} requires one of {tz_list}; "
                        f"got {user_data.timezone}"
                    )
            else:
                if user_data.timezone != tz_list[0]:
                    raise ValueError(
                        f"Invalid timezone {user_data.timezone} for {user_data.country}"
                    )
        else:
            if country_has_multiple_timezones(user_data.country):
                raise ValueError(
                    f"Country {user_data.country} has multiple timezones. "
                    "User must select specific timezone."
                )
            else:
                # Set timezone for single-timezone countries
                user_data.timezone = get_timezones_for_country(user_data.country)[0]

    # Validate timezone and country
    validate_timezone_and_country(user_data)

    # Create user record
    user = User(
        id=generate_user_id(),
        display_name=user_data.display_name,
        country=user_data.country.upper(),
        locale=user_data.locale,
        timezone=user_data.timezone,
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
        ValueError: If timezone update is invalid
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
        user_data.timezone = user_data.timezone.strip()
        if not user_data.timezone:
            raise ValueError("Timezone cannot be blank or whitespace-only.")

        # Validate timezone before updating
        if not validate_timezone(user_data.timezone):
            raise ValueError(f"Invalid timezone: {user_data.timezone}")

        # Only allow changing timezone for users in multi-timezone countries
        if not country_has_multiple_timezones(user.country):
            raise ValueError(
                f"Cannot change timezone for country {user.country}; use country-derived timezone"
            )

        allowed_tzs = get_timezones_for_country(user.country)
        if allowed_tzs and user_data.timezone not in allowed_tzs:
            raise ValueError(
                f"Timezone {user_data.timezone} is not valid for country {user.country}"
            )  # Shortened to comply with E501.

        user.timezone = user_data.timezone

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
