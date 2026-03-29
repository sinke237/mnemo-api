"""
Authentication service.
Handles JWT token generation, validation, and email-based login.
"""

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTError

from mnemo.core.config import get_settings
from mnemo.core.constants import PermissionScope

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from mnemo.models.user import User

settings = get_settings()


def create_access_token(
    user_id: str, scopes: list[str], expires_delta: timedelta | None = None
) -> str:
    """
    Create a JWT access token for a user.

    Args:
        user_id: User ID (usr_xxx)
        scopes: List of permission scopes
        expires_delta: Custom expiration time (defaults to JWT_EXPIRY_SECONDS)

    Returns:
        Encoded JWT token string
    """
    if expires_delta is None:
        expires_delta = timedelta(seconds=settings.jwt_expiry_seconds)

    expire = datetime.now(UTC) + expires_delta

    payload = {
        "sub": user_id,  # Subject: user ID
        "scopes": scopes,  # Permission scopes
        "exp": expire,  # Expiration time
        "iat": datetime.now(UTC),  # Issued at
    }

    encoded_jwt = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return cast(str, encoded_jwt)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """
    Decode and validate a JWT access token.

    Args:
        token: JWT token string

    Returns:
        Token payload if valid, None if expired or invalid
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        return payload
    except JWTError:
        return None


def decode_access_token_with_error(token: str) -> tuple[dict[str, Any] | None, str | None]:
    """
    Decode a JWT access token and distinguish invalid vs expired tokens.

    Returns:
        (payload, error) where error is "expired", "invalid", or None.
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        return payload, None
    except ExpiredSignatureError:
        return None, "expired"
    except JWTError:
        return None, "invalid"


def get_token_user_id(token: str) -> str | None:
    """
    Extract user_id from a JWT token.

    Args:
        token: JWT token string

    Returns:
        User ID if token is valid, None otherwise
    """
    payload = decode_access_token(token)
    if payload is None:
        return None
    return cast(str | None, payload.get("sub"))


def get_token_scopes(token: str) -> list[str]:
    """
    Extract scopes from a JWT token.

    Args:
        token: JWT token string

    Returns:
        List of scope strings, empty list if invalid
    """
    payload = decode_access_token(token)
    if payload is None:
        return []
    return cast(list[str], payload.get("scopes", []))


def token_has_scope(token: str, required_scope: PermissionScope) -> bool:
    """
    Check if a token has a specific permission scope.
    Admin scope grants all permissions.

    Args:
        token: JWT token string
        required_scope: Required permission scope

    Returns:
        True if token has the scope, False otherwise
    """
    scopes = get_token_scopes(token)

    # Admin scope grants everything
    if PermissionScope.ADMIN.value in scopes:
        return True

    return required_scope.value in scopes


def is_token_expired(token: str) -> bool:
    """
    Check if a token is expired.

    Args:
        token: JWT token string

    Returns:
        True if expired or invalid, False if still valid
    """
    payload = decode_access_token(token)
    if payload is None:
        return True

    exp = payload.get("exp")
    if exp is None:
        return True

    return datetime.now(UTC) > datetime.fromtimestamp(exp, tz=UTC)


async def authenticate_user_by_email(
    db: "AsyncSession",
    email: str,
    password: str,
) -> "User | None":
    """
    Verify email + password credentials.

    Returns the User record on success, or None if credentials are invalid.
    Deliberately returns None for both "user not found" and "wrong password"
    to prevent email enumeration.

    Args:
        db: Async database session
        email: The email address to look up
        password: The plain-text password to verify

    Returns:
        User record if credentials are valid, None otherwise
    """
    # Import here to avoid circular dependency at module load time
    from mnemo.services import user as user_service  # noqa: PLC0415
    from mnemo.utils.password import DUMMY_PASSWORD_HASH, verify_password  # noqa: PLC0415

    user = await user_service.get_user_by_email(db, email)
    # Always perform a bcrypt check path to avoid leaking timing information
    # about whether the user exists. If the user is missing or has no
    # password_hash, run a dummy verification against a valid bcrypt hash
    # and then return None.
    if user is None:
        verify_password(password, DUMMY_PASSWORD_HASH)
        return None

    if user.password_hash is None:
        # Account exists but has no password set — still run dummy verify
        verify_password(password, DUMMY_PASSWORD_HASH)
        return None

    # Real user with a password hash — perform normal verification
    if not verify_password(password, user.password_hash):
        return None

    return user


def scopes_for_role(role: str) -> list[str]:
    """
    Return JWT token scopes appropriate for the given user role.

    Note: The `admin_access_granted` flag is not used for authentication. Admin
    scope is determined solely by the `role` field. The `admin_access_granted`
    flag is separate and only controls whether admins are allowed to view a
    user's decks (consent), it does not affect role-based authentication.

    Args:
        role: User role string ("user" or "admin")

    Returns:
        List of scope value strings (e.g., ['decks:read', 'admin'])
    """
    from mnemo.core.constants import ADMIN_API_KEY_SCOPES, DEFAULT_API_KEY_SCOPES  # noqa: PLC0415

    if role == "admin":
        return [s.value for s in ADMIN_API_KEY_SCOPES]
    return [s.value for s in DEFAULT_API_KEY_SCOPES]
