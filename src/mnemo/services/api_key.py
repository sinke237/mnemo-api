"""
API Key service.
Handles API key creation, hashing, and validation.
Per spec section 02: Authentication and NFR-03.2.
"""

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime
from functools import lru_cache
from typing import cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.core.config import Settings, get_settings
from mnemo.core.constants import (
    ALLOWED_API_KEY_PREFIXES,
    ALLOWED_API_KEY_TYPES,
    DEFAULT_API_KEY_SCOPES,
    PermissionScope,
)
from mnemo.models.api_key import APIKey
from mnemo.services import user as user_service
from mnemo.utils.id_generator import generate_api_key


@lru_cache
def _signing_key() -> bytes:
    """Return the HMAC signing key derived from the application secret."""
    settings: Settings = get_settings()
    api_key_secret = str(settings.api_key_secret)  # Ensure it's a string
    return api_key_secret.encode("utf-8")


def hash_api_key(api_key: str) -> str:
    """
    Hash an API key using HMAC-SHA-256 keyed on the application secret.
    Per spec NFR-03.2: API keys must be stored hashed, never in plaintext.

    Using HMAC-SHA-256 instead of bcrypt because:
    - API keys are long random tokens (not user passwords); slow hashing adds
      latency without meaningful security benefit.
    - bcrypt has a hard 72-byte limit that our 73-byte keys exceed.
    - HMAC-SHA-256 is constant-time when compared with hmac.compare_digest.

    Args:
        api_key: Full API key (e.g., mnm_live_abcdef...)

    Returns:
        Hex-encoded HMAC-SHA-256 digest
    """
    return hmac.new(_signing_key(), api_key.encode(), hashlib.sha256).hexdigest()


def verify_api_key(api_key: str, key_hash: str) -> bool:
    """
    Verify an API key against its stored HMAC-SHA-256 hash.
    Uses hmac.compare_digest for constant-time comparison.

    Args:
        api_key: Plain API key from request
        key_hash: Stored HMAC-SHA-256 hex digest

    Returns:
        True if key matches hash, False otherwise
    """
    expected = hash_api_key(api_key)
    return hmac.compare_digest(expected, key_hash)


async def create_api_key(
    db: AsyncSession,
    user_id: str,
    name: str | None = None,
    is_live: bool = False,
    scopes: list[PermissionScope] | None = None,
) -> tuple[APIKey, str]:
    """
    Create a new API key for a user.

    Returns both the database record AND the plain key.
    The plain key is shown only once and must be saved by the caller.

    Args:
        db: Database session
        user_id: User ID (usr_xxx)
        name: Optional descriptive name
        is_live: True for live key (mnm_live_), False for test key (mnm_test_)
        scopes: List of permission scopes (defaults to standard scopes)

    Returns:
        Tuple of (APIKey record, plain_api_key)
    """
    # Generate the plain key
    plain_key = generate_api_key(is_live=is_live)

    # Extract prefix and hint
    prefix = extract_api_key_prefix(plain_key)
    key_hint = plain_key[-4:]  # Last 4 chars for UI display

    # Hash the key
    key_hash = hash_api_key(plain_key)
    # Short lookup fragment (first 16 hex chars of HMAC) to index candidate set
    key_lookup = key_hash[:16]

    # Default scopes
    if scopes is None:
        scopes = DEFAULT_API_KEY_SCOPES

    # Create record
    api_key_record = APIKey(
        id=f"key_{uuid.uuid4().hex}",  # Cryptographically secure UUID4-based ID
        user_id=user_id,
        key_hash=key_hash,
        key_lookup=key_lookup,
        key_prefix=prefix,
        key_hint=key_hint,
        name=name,
        is_live=is_live,
        scopes=json.dumps([scope.value for scope in scopes]),
        is_active=True,
    )

    # Ensure referenced user exists to avoid creating orphaned API keys.
    user_exists = await user_service.user_exists(db, user_id)
    if not user_exists:
        raise ValueError("User not found")

    db.add(api_key_record)
    # Flush and handle potential integrity errors (race or DB-level FK enforcement)
    try:
        await db.flush()
    except IntegrityError as exc:
        # Re-raise as ValueError so callers can handle a consistent exception type
        raise ValueError("Referential integrity error creating API key") from exc

    return api_key_record, plain_key


async def get_api_key_by_hash(db: AsyncSession, key_hash: str) -> APIKey | None:
    """
    Retrieve an API key record by its hash.

    Args:
        db: Database session
        key_hash: HMAC-SHA-256 hex digest of the full key

    Returns:
        APIKey record or None if not found
    """
    result = await db.execute(select(APIKey).where(APIKey.key_hash == key_hash))
    return result.scalar_one_or_none()


async def validate_api_key(db: AsyncSession, plain_key: str) -> APIKey | None:
    """
    Validate an API key and return the associated record if valid.

    This is the main validation function used by auth middleware.
    Checks:
    1. Key format is valid
    2. Key exists in database
    3. Key is active (not revoked)
    4. Updates last_used_at timestamp

    Args:
        db: Database session
        plain_key: Plain API key from request header

    Returns:
        APIKey record if valid and active, None otherwise
    """
    # Extract prefix for quick lookup
    try:
        prefix = extract_api_key_prefix(plain_key)
    except ValueError:
        return None  # Malformed key

    # Compute lookup fragment and find all active keys matching prefix+lookup
    lookup = hash_api_key(plain_key)[:16]
    # Temporal fallback: APIKey.key_lookup might be NULL for pre-migration keys.
    # We include them by checking for None, leaving downstream hash check intact.
    # Follow-up task: backfill key_lookup in a separate migration when
    # a safe deterministic lookup can be computed.
    result = await db.execute(
        select(APIKey).where(
            APIKey.key_prefix == prefix,
            APIKey.is_active == True,  # noqa: E712
            (APIKey.key_lookup == lookup) | APIKey.key_lookup.is_(None),
        )
    )
    candidates = result.scalars().all()

    # Check hash for each candidate
    for candidate in candidates:
        if verify_api_key(plain_key, candidate.key_hash):
            # Valid key found - update last_used_at
            candidate.last_used_at = datetime.now(UTC)
            await db.flush()
            return candidate

    return None  # No match found


async def revoke_api_key(db: AsyncSession, key_id: str) -> bool:
    """
    Revoke an API key (mark as inactive).

    Args:
        db: Database session
        key_id: API key ID

    Returns:
        True if key was found and revoked, False otherwise
    """
    result = await db.execute(select(APIKey).where(APIKey.id == key_id))
    key = result.scalar_one_or_none()

    if key is None:
        return False

    key.is_active = False
    key.revoked_at = datetime.now(UTC)
    await db.flush()

    return True


def get_key_scopes(api_key: APIKey) -> list[str]:
    """
    Extract permission scopes from an API key record.

    Args:
        api_key: APIKey record

    Returns:
        List of scope strings (e.g., ['decks:read', 'decks:write'])
    """
    try:
        return cast(list[str], json.loads(api_key.scopes))
    except (json.JSONDecodeError, TypeError):
        return []


def has_scope(api_key: APIKey, required_scope: PermissionScope) -> bool:
    """
    Check if an API key has a specific permission scope.
    Admin scope grants all permissions.

    Args:
        api_key: APIKey record
        required_scope: Required permission scope

    Returns:
        True if key has the scope, False otherwise
    """
    scopes = get_key_scopes(api_key)

    # Admin scope grants everything
    if PermissionScope.ADMIN.value in scopes:
        return True

    return required_scope.value in scopes


def extract_api_key_prefix(plain_key: str) -> str:
    """
    Extract the prefix from a plain API key (e.g., 'mnm_live_').

    Args:
        plain_key: The plain API key

    Returns:
        The extracted prefix string

    Raises:
        ValueError: If the key format is malformed or invalid
    """
    if not plain_key or not plain_key.strip():
        raise ValueError("API key cannot be empty or whitespace-only")

    parts = plain_key.split("_")
    if len(parts) < 3 or not parts[2].strip():
        raise ValueError("Malformed API key: expected at least two segments and non-empty payload")

    # Optionally validate parts[0] and parts[1] against an allowlist of known prefixes
    if parts[0] not in ALLOWED_API_KEY_PREFIXES:
        raise ValueError(f"Unknown prefix: {parts[0]}")

    if parts[1] not in ALLOWED_API_KEY_TYPES:
        raise ValueError(f"Unknown key type: {parts[1]}")

    return f"{parts[0]}_{parts[1]}_"
