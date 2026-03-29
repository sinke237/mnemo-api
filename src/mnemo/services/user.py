"""
User service.
Unified user provisioning with email support and proper API key creation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.core.constants import ADMIN_API_KEY_SCOPES, DEFAULT_API_KEY_SCOPES
from mnemo.core.exceptions import (
    DisplayNameConflictError,
    EmailConflictError,
    InvalidCountryCodeError,
    InvalidTimezoneError,
    MissingTimezoneError,
    TimezoneNotAllowedError,
)
from mnemo.models.deck import Deck
from mnemo.models.user import User
from mnemo.schemas.user import UserProvisionRequest, UserUpdate
from mnemo.utils.id_generator import generate_user_id
from mnemo.utils.password import get_password_hash
from mnemo.utils.timezone import (
    country_has_multiple_timezones,
    get_timezones_for_country,
    validate_timezone,
)

if TYPE_CHECKING:
    from mnemo.models.user_admin_consent import UserAdminConsent


def normalize_email(email: str) -> str:
    """
    Normalize an email address for case-insensitive uniqueness checks.

    Args:
        email: Raw email address

    Returns:
        Normalized email (lowercase, stripped)
    """
    return email.strip().lower()


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


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """
    Retrieve a user by email address (case-insensitive).

    Args:
        db: Database session
        email: Email address

    Returns:
        User record or None if not found
    """
    normalized = normalize_email(email)
    result = await db.execute(select(User).where(User.normalized_email == normalized))
    user = result.scalar_one_or_none()
    if user is not None:
        return user

    # Fallback: during staged email collection some addresses may be stored
    # in `normalized_email_placeholder`. Allow lookup there to preserve
    # legacy login paths while operators are validating and migrating
    # placeholder addresses into the primary `email` column.
    result = await db.execute(select(User).where(User.normalized_email_placeholder == normalized))
    return result.scalar_one_or_none()


async def get_user_by_display_name(db: AsyncSession, display_name: str) -> User | None:
    """Retrieve a user by their display_name (normalized match)."""
    normalized = display_name.strip().lower()
    result = await db.execute(select(User).where(User.normalized_display_name == normalized))
    return result.scalar_one_or_none()


async def email_taken(db: AsyncSession, email: str) -> bool:
    """Return True if email is already used by another user (case-insensitive match)."""
    normalized = normalize_email(email)
    result = await db.execute(select(1).where(User.normalized_email == normalized).limit(1))
    return result.scalar_one_or_none() is not None


async def display_name_taken(db: AsyncSession, display_name: str) -> bool:
    """Return True if display_name is already used by another user (normalized match)."""
    normalized = display_name.strip().lower()
    result = await db.execute(select(1).where(User.normalized_display_name == normalized).limit(1))
    return result.scalar_one_or_none() is not None


async def user_exists(db: AsyncSession, user_id: str) -> bool:
    """
    Check if a user exists.

    Args:
        db: Database session
        user_id: User ID (usr_xxx)

    Returns:
        True if user exists, False otherwise
    """
    result = await db.execute(select(1).where(User.id == user_id).limit(1))
    return result.scalar_one_or_none() is not None


async def provision_user(
    db: AsyncSession,
    email: str,
    password: str,
    country: str,
    timezone: str | None = None,
    display_name: str | None = None,
    role: str = "user",
    create_live_key: bool = False,
) -> tuple[User, str, str]:
    """
    UNIFIED user provisioning function.

    Creates a new user account with email, password, and automatically generates
    an API key (test or live based on create_live_key parameter).

    Used by both:
    - POST /v1/user/provision (public self-registration) - always creates test keys
    - POST /v1/admin/provision (admin user creation) - can create live keys

    Args:
        db: Database session
        email: Email address (must be unique)
        password: Plain-text password (will be hashed)
        country: ISO 3166-1 alpha-2 country code (will be uppercased)
        timezone: Optional IANA timezone (required for multi-timezone countries)
        display_name: Optional unique display name
        role: "user" or "admin" (default "user")
        create_live_key: If True, create live API key; otherwise test key (default False)

    Returns:
        Tuple of (User record, plain API key string, key_type "test" or "live")

    Raises:
        EmailConflictError: If email is already taken
        DisplayNameConflictError: If display_name is already taken
        InvalidCountryCodeError: Invalid country code
        InvalidTimezoneError: Invalid or mismatched timezone
        MissingTimezoneError: Multi-TZ country but no timezone provided
    """
    # Import here to avoid circular dependency
    from mnemo.services import api_key as api_key_service  # noqa: PLC0415

    country = country.upper()
    normalized_email = normalize_email(email)

    # Check email uniqueness before hitting the DB constraint
    if await email_taken(db, email):
        raise EmailConflictError(f"Email '{email}' is already registered")

    # Check display_name uniqueness if provided
    if display_name and await display_name_taken(db, display_name):
        raise DisplayNameConflictError(f"Display name '{display_name}' is already taken")

    # Resolve timezone
    resolved_timezone = resolve_country_timezone(country, timezone)

    # Hash password
    hashed = get_password_hash(password)

    # Create user record
    user = User(
        id=generate_user_id(),
        email=email,
        normalized_email=normalized_email,
        email_verified=False,  # TODO: Send verification email
        password_hash=hashed,
        display_name=display_name,
        normalized_display_name=(
            display_name.strip().lower() if display_name is not None else None
        ),
        country=country,
        timezone=resolved_timezone,
        role=role,
    )
    db.add(user)

    try:
        await db.flush()
    except IntegrityError as exc:
        # Handle race conditions where email/display_name is taken between check and insert
        _exc_text = str(exc.orig) if exc.orig else str(exc)
        if "uq_users_email" in _exc_text or "uq_users_normalized_email" in _exc_text:
            raise EmailConflictError(f"Email '{email}' is already registered") from None
        if "uq_users_display_name" in _exc_text or "uq_users_normalized_display_name" in _exc_text:
            raise DisplayNameConflictError(
                f"Display name '{display_name}' is already taken"
            ) from None
        raise

    # Determine API key scopes based on role. The module-level constants
    # `ADMIN_API_KEY_SCOPES` and `DEFAULT_API_KEY_SCOPES` already contain
    # `PermissionScope` members — copy them rather than re-wrapping to avoid
    # unnecessary construction and potential mutation of the originals.
    scopes = list(ADMIN_API_KEY_SCOPES) if role == "admin" else list(DEFAULT_API_KEY_SCOPES)

    # Create API key (test or live based on parameter)
    _, plain_api_key = await api_key_service.create_api_key(
        db=db,
        user_id=user.id,
        name="Default",
        is_live=create_live_key,
        scopes=scopes,
    )

    key_type = "live" if create_live_key else "test"

    return user, plain_api_key, key_type


async def create_user(db: AsyncSession, user_data: UserProvisionRequest) -> User:
    """
    Compatibility helper used by tests: create a user from a request-like object.

    Delegates to `provision_user` and returns only the `User` record.
    """
    user, _plain_api_key, _key_type = await provision_user(
        db=db,
        email=user_data.email,
        password=user_data.password,
        country=user_data.country,
        timezone=getattr(user_data, "timezone", None),
        display_name=getattr(user_data, "display_name", None),
        role=getattr(user_data, "role", "user") or "user",
        create_live_key=False,
    )
    return user


async def update_user(db: AsyncSession, user_id: str, user_data: UserUpdate) -> User | None:
    """
    Update user profile fields.

    Note: country and email cannot be changed after creation.
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


async def create_admin_consent(
    db: AsyncSession,
    user_id: str,
    resource: str,
    resource_id: str | None = None,
    expires_at: datetime | None = None,
) -> UserAdminConsent:
    """Create a per-resource admin consent record for a user.

    Note: ID generation uses existing id generator for users; we can reuse it here.
    """
    import secrets

    # Check for an existing consent first to avoid duplicate global consents
    from sqlalchemy import select

    from mnemo.models.user_admin_consent import UserAdminConsent

    if resource_id is None:
        existing_stmt = select(UserAdminConsent).where(
            UserAdminConsent.user_id == user_id,
            UserAdminConsent.resource_type == resource,
            UserAdminConsent.resource_id.is_(None),
        )
    else:
        existing_stmt = select(UserAdminConsent).where(
            UserAdminConsent.user_id == user_id,
            UserAdminConsent.resource_type == resource,
            UserAdminConsent.resource_id == resource_id,
        )

    result = await db.execute(existing_stmt.limit(1))
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing

    consent = UserAdminConsent(
        id=f"cnst_{secrets.token_hex(8)}",
        user_id=user_id,
        resource_type=resource,
        resource_id=resource_id,
        granted_at=datetime.now(UTC),
        expires_at=expires_at,
    )
    db.add(consent)
    try:
        await db.flush()
    except IntegrityError:
        # Concurrent insert created the same consent — return the existing one
        result = await db.execute(existing_stmt.limit(1))
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing
        # If still not found, re-raise for visibility
        raise
    return consent


async def revoke_admin_consent(
    db: AsyncSession, user_id: str, resource: str | None = None, resource_id: str | None = None
) -> int:
    """Revoke matching admin consents. Returns number of deleted rows."""
    from sqlalchemy import delete

    from mnemo.models.user_admin_consent import UserAdminConsent

    stmt = delete(UserAdminConsent).where(UserAdminConsent.user_id == user_id)
    if resource is not None:
        stmt = stmt.where(UserAdminConsent.resource_type == resource)
    if resource_id is not None:
        stmt = stmt.where(UserAdminConsent.resource_id == resource_id)

    result = await db.execute(stmt)
    await db.flush()
    return result.rowcount or 0


async def has_admin_consent(
    db: AsyncSession, user_id: str, resource: str, resource_id: str | None = None
) -> bool:
    """Return True if the user has granted admin consent for the given resource.

    Consent matches if there is a record where resource_type == resource and
    (resource_id is NULL OR resource_id == requested resource_id).
    """
    from sqlalchemy import or_

    from mnemo.models.user_admin_consent import UserAdminConsent

    # Only consider consents that are non-expiring or have not yet expired.
    now = datetime.now(UTC)

    # Match global consent for that resource type (resource_id is NULL)
    if resource_id is not None:
        stmt = select(UserAdminConsent).where(
            UserAdminConsent.user_id == user_id,
            UserAdminConsent.resource_type == resource,
            or_(
                UserAdminConsent.resource_id.is_(None), UserAdminConsent.resource_id == resource_id
            ),
            or_(UserAdminConsent.expires_at.is_(None), UserAdminConsent.expires_at > now),
        )
    else:
        stmt = select(UserAdminConsent).where(
            UserAdminConsent.user_id == user_id,
            UserAdminConsent.resource_type == resource,
            or_(UserAdminConsent.expires_at.is_(None), UserAdminConsent.expires_at > now),
        )

    result = await db.execute(stmt.limit(1))
    return result.scalar_one_or_none() is not None


async def list_users(
    db: AsyncSession,
    page: int = 1,
    per_page: int = 20,
    search: str | None = None,
) -> tuple[list[tuple[User, int]], int]:
    """
    List all users with deck counts (admin use).

    Args:
        db: Database session
        page: Page number (1-based)
        per_page: Items per page (max 100)
        search: Optional partial match on display_name or email

    Returns:
        Tuple of (list of (User, deck_count) pairs, total user count)
    """
    page = max(page, 1)
    per_page = min(max(per_page, 1), 100)

    # Correlated scalar subquery for deck count
    deck_count_col = (
        select(func.count(Deck.id)).where(Deck.user_id == User.id).correlate(User).scalar_subquery()
    ).label("deck_count")

    # Base filter
    where_clauses = []
    if search:
        # Escape SQL wildcard characters
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        # Search both display_name and email
        where_clauses.append(
            (User.display_name.ilike(f"%{escaped}%", escape="\\"))
            | (User.email.ilike(f"%{escaped}%", escape="\\"))
        )

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
