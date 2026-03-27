"""
User service.
Handles user CRUD operations and profile management.
Per spec section 11: User Profiles.
"""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.core.constants import ADMIN_API_KEY_SCOPES, DEFAULT_API_KEY_SCOPES, PermissionScope
from mnemo.core.exceptions import (
    DisplayNameConflictError,
    InvalidCountryCodeError,
    InvalidTimezoneError,
    MissingTimezoneError,
    TimezoneNotAllowedError,
)
from mnemo.models.deck import Deck
from mnemo.models.user import User
from mnemo.schemas.user import UserCreate, UserUpdate
from mnemo.utils.id_generator import generate_user_id
from mnemo.utils.password import get_password_hash
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


def resolve_country_timezone(country: str, timezone: str | None) -> str:
    """
    Resolve and validate the timezone for a given country.

    Args:
        country: Uppercase ISO 3166-1 alpha-2 country code
        timezone: Optional IANA timezone string provided by the caller

    Returns:
        Resolved IANA timezone string

    Raises:
        InvalidCountryCodeError: If the country code is not supported
        InvalidTimezoneError: If the provided timezone is invalid for the country
        MissingTimezoneError: If timezone is required but not provided
    """
    tz_list: list[str] = get_timezones_for_country(country)
    if not tz_list:
        raise InvalidCountryCodeError(f"Unsupported country code: {country}")

    if timezone is not None:
        normalized = normalize_and_precheck_timezone(timezone)
        if country_has_multiple_timezones(country):
            if normalized not in tz_list:
                raise InvalidTimezoneError(
                    f"Country {country} requires one of {tz_list}; got {normalized}"
                )
        else:
            if normalized != tz_list[0]:
                raise InvalidTimezoneError(f"Invalid timezone {normalized} for {country}")
        return normalized
    else:
        if country_has_multiple_timezones(country):
            raise MissingTimezoneError(
                f"Country {country} has multiple timezones. " "User must select specific timezone."
            )
        return tz_list[0]


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
    resolved_timezone = resolve_country_timezone(user_data.country, user_data.timezone)

    # Create user record
    normalized_display_name = (
        user_data.display_name.strip().lower() if user_data.display_name is not None else None
    )

    user = User(
        id=generate_user_id(),
        display_name=user_data.display_name,
        normalized_display_name=normalized_display_name,
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
        user.normalized_display_name = user_data.display_name.strip().lower()

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


async def get_user_by_display_name(db: AsyncSession, display_name: str) -> User | None:
    """Retrieve a user by their display_name (normalized match)."""
    normalized = display_name.strip().lower()
    result = await db.execute(select(User).where(User.normalized_display_name == normalized))
    return result.scalar_one_or_none()


async def display_name_taken(db: AsyncSession, display_name: str) -> bool:
    """Return True if display_name is already used by another user (normalized match)."""
    normalized = display_name.strip().lower()
    result = await db.execute(select(1).where(User.normalized_display_name == normalized).limit(1))
    return result.scalar_one_or_none() is not None


async def provision_user(
    db: AsyncSession,
    display_name: str | None,
    country: str,
    timezone: str | None,
    password: str | None,
    role: str = "user",
) -> tuple["User", str]:
    """
    Create a new user account via self-registration or admin provisioning.

    Validates country/timezone, optionally hashes the password, and creates a
    companion API key.  Returns (user, plain_api_key) — the plain key is shown
    only once and must be returned to the caller immediately.

    Args:
        db: Database session
        display_name: Optional unique display name
        country: ISO 3166-1 alpha-2 country code (will be uppercased)
        timezone: Optional IANA timezone (required for multi-timezone countries)
        password: Optional plain-text password (min 8 chars; stored hashed)
        role: "user" or "admin" (default "user")

    Returns:
        Tuple of (User record, plain API key string)

    Raises:
        DisplayNameConflictError: If display_name is already taken
        InvalidCountryCodeError: Invalid country code
        InvalidTimezoneError: Invalid or mismatched timezone
        MissingTimezoneError: Multi-TZ country but no timezone provided
    """
    # Inline import avoids circular dependency (api_key_service imports user_service)
    from mnemo.services import api_key as api_key_service  # noqa: PLC0415

    country = country.upper()

    # Check display_name uniqueness before hitting the DB constraint
    if display_name and await display_name_taken(db, display_name):
        raise DisplayNameConflictError(f"Display name '{display_name}' is already taken")

    resolved_timezone = resolve_country_timezone(country, timezone)

    # Hash password if provided; passwordless accounts stay at NULL
    hashed: str | None = get_password_hash(password) if password else None

    user = User(
        id=generate_user_id(),
        display_name=display_name,
        normalized_display_name=(
            display_name.strip().lower() if display_name is not None else None
        ),
        country=country,
        timezone=resolved_timezone,
        role=role,
        password_hash=hashed,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        # Race condition: another request inserted the same display_name
        raise DisplayNameConflictError(  # noqa: B904
            f"Display name '{display_name}' is already taken"
        ) from None

    # Determine API key scopes based on role
    scopes = (
        [PermissionScope(s) for s in ADMIN_API_KEY_SCOPES]
        if role == "admin"
        else [PermissionScope(s) for s in DEFAULT_API_KEY_SCOPES]
    )
    _, plain_api_key = await api_key_service.create_api_key(
        db=db,
        user_id=user.id,
        name="Default",
        is_live=False,
        scopes=scopes,
    )

    return user, plain_api_key


async def list_users(
    db: AsyncSession,
    page: int = 1,
    per_page: int = 20,
    search: str | None = None,
) -> tuple[list[tuple["User", int]], int]:
    """
    List all users with deck counts (admin use).

    Args:
        db: Database session
        page: Page number (1-based)
        per_page: Items per page (max 100)
        search: Optional partial match on display_name

    Returns:
        Tuple of (list of (User, deck_count) pairs, total user count)
    """
    page = max(page, 1)
    per_page = min(max(per_page, 1), 100)

    # Correlated scalar subquery for deck count to avoid GROUP BY complexity
    deck_count_col = (
        select(func.count(Deck.id)).where(Deck.user_id == User.id).correlate(User).scalar_subquery()
    ).label("deck_count")

    # Base filter
    where_clauses = []
    if search:
        # Escape backslashes first, then SQL wildcard characters so literal
        # backslashes, percent signs and underscores in the search string are
        # treated as literals rather than wildcards.
        escaped = (
            search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
        where_clauses.append(User.display_name.ilike(f"%{escaped}%", escape="\\"))

    # Total count
    count_stmt = select(func.count(User.id)).select_from(User)
    if where_clauses:
        count_stmt = count_stmt.where(*where_clauses)
    total = int(await db.scalar(count_stmt) or 0)

    # Paginated data
    stmt = (
        select(User, deck_count_col)
        .order_by(User.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    if where_clauses:
        stmt = stmt.where(*where_clauses)

    result = await db.execute(stmt)
    rows: list[tuple[User, int]] = [(user, int(count or 0)) for user, count in result.all()]
    return rows, total
