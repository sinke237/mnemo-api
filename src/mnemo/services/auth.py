"""
Authentication service.
Handles JWT token generation and validation.
Per spec section 02: Authentication.
"""

from datetime import UTC, datetime, timedelta
from typing import Any, cast

from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTError

from mnemo.core.config import get_settings
from mnemo.core.constants import PermissionScope

settings = get_settings()


def create_access_token(
    user_id: str, scopes: list[str], expires_delta: timedelta | None = None
) -> str:
    """
    Create a JWT access token for a user.

    Per spec:
    - Tokens expire after 1 hour (configurable via JWT_EXPIRY_SECONDS)
    - Token includes user_id and scopes from the API key
    - Scopes cannot exceed what the API key has

    Args:
        user_id: User ID (usr_xxx)
        scopes: List of permission scopes (from API key)
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
