"""Password reset token service scaffolding.

Provides helpers to create and consume password reset tokens. Tokens are
returned to the caller in plaintext once and stored hashed in the database.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.core.config import get_settings
from mnemo.models.password_reset_token import PasswordResetToken


def _hash_token(token: str) -> str:
    settings = get_settings()
    key = settings.password_reset_secret.encode()
    return hmac.new(key, token.encode(), hashlib.sha256).hexdigest()


async def create_token(
    db: AsyncSession, user_id: str, ttl_seconds: int = 3600, ip_address: str | None = None
) -> str:
    """Create a password reset token for `user_id` and persist a hash.

    Returns the plaintext token which should be emailed to the user once.
    """
    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)

    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=ttl_seconds)

    prt = PasswordResetToken(
        id=f"prt_{secrets.token_hex(8)}",
        token_hash=token_hash,
        user_id=user_id,
        issued_at=now,
        expires_at=expires_at,
        used_at=None,
        ip_address=ip_address,
    )
    db.add(prt)
    await db.flush()
    return token


async def delete_expired_tokens(db: AsyncSession, older_than_seconds: int = 0) -> int:
    """Delete password reset tokens that expired more than `older_than_seconds` ago.

    Returns the number of rows deleted.
    """
    from datetime import UTC, datetime, timedelta

    cutoff = datetime.now(UTC) - timedelta(seconds=older_than_seconds)
    result = await db.execute(
        delete(PasswordResetToken).where(PasswordResetToken.expires_at < cutoff)
    )
    # SQLAlchemy Core delete doesn't return rowcount reliably across DBs; flush to apply
    await db.flush()
    try:
        return result.rowcount or 0
    except Exception:
        return 0


async def get_token_by_plain(db: AsyncSession, token: str) -> PasswordResetToken | None:
    """Lookup a token record by plaintext token.

    Returns the token row if present, not used, and not expired.
    """
    token_hash = _hash_token(token)
    now = datetime.now(UTC)
    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
    )
    return result.scalar_one_or_none()


async def mark_token_used(db: AsyncSession, token_id: str) -> None:
    now = datetime.now(UTC)
    # Mark used_at timestamp to prevent reuse
    result = await db.execute(select(PasswordResetToken).where(PasswordResetToken.id == token_id))
    row = result.scalar_one_or_none()
    if row is None:
        return
    row.used_at = now
    await db.flush()
