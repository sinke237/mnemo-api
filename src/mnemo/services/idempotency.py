"""
Idempotency service.
Stores and replays responses for idempotent POST requests.
Per spec NFR-03.7 and Idempotency section (24h TTL).
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.models.idempotency_key import IdempotencyKey

IDEMPOTENCY_TTL = timedelta(hours=24)


async def get_idempotency_record(
    db: AsyncSession,
    user_id: str,
    endpoint: str,
    key: str,
) -> IdempotencyKey | None:
    """Return a valid idempotency record if present and not expired."""
    result = await db.execute(
        select(IdempotencyKey).where(
            IdempotencyKey.user_id == user_id,
            IdempotencyKey.endpoint == endpoint,
            IdempotencyKey.key == key,
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        return None

    now = datetime.now(UTC)
    created_at = record.created_at
    if created_at is None:
        return None
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)

    if created_at < now - IDEMPOTENCY_TTL:
        # Expired: delete and treat as new
        await db.delete(record)
        await db.flush()
        return None

    return record


async def store_idempotency_record(
    db: AsyncSession,
    user_id: str,
    endpoint: str,
    key: str,
    status_code: int,
    response_body: dict[str, Any],
) -> IdempotencyKey:
    """Store an idempotency record for a successful POST response."""
    record = IdempotencyKey(
        id=f"idem_{uuid.uuid4().hex}",
        user_id=user_id,
        endpoint=endpoint,
        key=key,
        status_code=status_code,
        response_body=response_body,
    )
    db.add(record)
    try:
        await db.flush()
    except IntegrityError:
        # Another request stored it concurrently; fetch and return existing
        await db.rollback()
        existing = await get_idempotency_record(db, user_id, endpoint, key)
        if existing is None:
            raise
        return existing
    return record
