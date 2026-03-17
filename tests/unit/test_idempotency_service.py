"""
Unit tests for the idempotency service.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.core.exceptions import IdempotencyConflictError
from mnemo.models.idempotency_key import IdempotencyKey
from mnemo.services.idempotency import get_idempotency_record


@pytest.fixture
def mock_db_session():
    """Fixture for a mocked async database session."""
    return AsyncSession()


@pytest.mark.asyncio
async def test_get_idempotency_record_reserved_raises_conflict(mock_db_session):
    user_id = "test_user"
    endpoint = "/test"
    key = "test_key"

    # Create a mock record that is reserved but not finalized
    reserved_record = IdempotencyKey(
        user_id=user_id,
        endpoint=endpoint,
        key=key,
        status_code=0,  # Reserved
        created_at=datetime.now(UTC),
    )

    # Mock the database to return the reserved record
    mock_db_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=lambda: reserved_record)
    )

    with pytest.raises(IdempotencyConflictError):
        await get_idempotency_record(mock_db_session, user_id, endpoint, key)
