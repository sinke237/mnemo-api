"""
Unit tests for the idempotency service.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from mnemo.core.exceptions import IdempotencyConflictError
from mnemo.models.idempotency_key import IdempotencyKey
from mnemo.services.idempotency import get_idempotency_record


@pytest.mark.asyncio
async def test_get_idempotency_record_reserved_raises_conflict(
    mock_db_session: AsyncMock,
):
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
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = reserved_record
    mock_db_session.execute.return_value = mock_result

    with pytest.raises(IdempotencyConflictError):
        await get_idempotency_record(mock_db_session, user_id, endpoint, key)

    # Assert that the database was queried correctly
    mock_db_session.execute.assert_awaited_once()
    statement = mock_db_session.execute.call_args[0][0]
    query_str = str(statement.compile(compile_kwargs={"literal_binds": True})).lower()
    assert f"user_id = '{user_id}'".lower() in query_str
    assert f"endpoint = '{endpoint}'".lower() in query_str
    assert f"key = '{key}'".lower() in query_str

    # Assert that no other database operations were performed
    mock_db_session.add.assert_not_called()
    mock_db_session.commit.assert_not_called()
    mock_db_session.flush.assert_not_called()
    mock_db_session.delete.assert_not_called()
