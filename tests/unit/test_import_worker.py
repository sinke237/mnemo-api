"""
Unit tests for the import worker.
Mocks database and Redis interactions to test worker logic.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.core.constants import ImportJobStatus
from mnemo.models.import_job import ImportJob
from mnemo.workers.import_worker import (
    _process_db_job,
    _process_job,
    _process_redis_job,
    run_worker,
)


@pytest.fixture
def mock_db_session():
    """Fixture for a mocked async database session."""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def mock_import_service():
    """Fixture for mocking the import_service."""
    with patch("mnemo.workers.import_worker.import_service", autospec=True) as mock:
        yield mock


@pytest.mark.asyncio
async def test_process_job_success(mock_db_session, mock_import_service):
    job_id = "test_job_id"
    job = ImportJob(id=job_id, status=ImportJobStatus.QUEUED.value)
    mock_db_session.get.return_value = job

    result = await _process_job(mock_db_session, job_id)

    assert result is True
    mock_import_service.process_import_job.assert_called_once_with(mock_db_session, job_id)
    mock_db_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_process_job_not_found(mock_db_session, mock_import_service):
    job_id = "not_found_id"
    mock_db_session.get.return_value = None

    result = await _process_job(mock_db_session, job_id)

    assert result is False
    mock_import_service.process_import_job.assert_not_called()


@pytest.mark.asyncio
async def test_process_job_wrong_status(mock_db_session, mock_import_service):
    job_id = "test_job_id"
    job = ImportJob(id=job_id, status=ImportJobStatus.PROCESSING.value)
    mock_db_session.get.return_value = job

    result = await _process_job(mock_db_session, job_id)

    assert result is False
    mock_import_service.process_import_job.assert_not_called()


@pytest.mark.asyncio
@patch("mnemo.workers.import_worker._dequeue_job_id")
@patch("mnemo.workers.import_worker.AsyncSessionLocal")
async def test_process_redis_job_dequeues_and_processes(
    mock_session_local, mock_dequeue, mock_import_service, mock_db_session
):
    job_id = "redis_job_id"
    mock_dequeue.return_value = job_id
    mock_session_local.return_value.__aenter__.return_value = mock_db_session
    with patch("mnemo.workers.import_worker._process_job") as mock_process:
        mock_process.return_value = True
        result = await _process_redis_job()

    assert result is True
    mock_dequeue.assert_called_once()
    mock_process.assert_called_once_with(mock_db_session, job_id)


@pytest.mark.asyncio
@patch("mnemo.workers.import_worker._dequeue_job_id")
async def test_process_redis_job_nothing_to_dequeue(mock_dequeue):
    mock_dequeue.return_value = None
    result = await _process_redis_job()
    assert result is False


@pytest.mark.asyncio
@patch("mnemo.workers.import_worker._claim_db_job")
@patch("mnemo.workers.import_worker.AsyncSessionLocal")
async def test_process_db_job_claims_and_processes(
    mock_session_local, mock_claim, mock_import_service, mock_db_session
):
    job_id = "db_job_id"
    claimed_job = ImportJob(id=job_id, status=ImportJobStatus.QUEUED.value)
    mock_claim.return_value = claimed_job
    mock_session_local.return_value.__aenter__.return_value = mock_db_session

    # Mock the database check for queued jobs
    mock_execute = AsyncMock()
    mock_scalar = MagicMock()
    mock_scalar.scalar_one_or_none.return_value = "some_id"  # Indicates a job is queued
    mock_execute.return_value = mock_scalar
    mock_db_session.execute = mock_execute

    with patch("mnemo.workers.import_worker._process_job") as mock_process:
        mock_process.return_value = True
        result = await _process_db_job()

    assert result is True
    mock_claim.assert_called_once_with(mock_db_session)
    mock_process.assert_called_once_with(mock_db_session, job_id)


@pytest.mark.asyncio
@patch("mnemo.workers.import_worker.AsyncSessionLocal")
async def test_process_db_job_no_queued_jobs(mock_session_local, mock_db_session):
    # Mock the database check for queued jobs
    mock_execute = AsyncMock()
    mock_scalar = MagicMock()
    mock_scalar.scalar_one_or_none.return_value = None  # No jobs queued
    mock_execute.return_value = mock_scalar
    mock_db_session.execute = mock_execute
    mock_session_local.return_value.__aenter__.return_value = mock_db_session

    result = await _process_db_job()
    assert result is False


@pytest.mark.asyncio
@patch("mnemo.workers.import_worker.asyncio.sleep", new_callable=AsyncMock)
@patch("mnemo.workers.import_worker._process_redis_job", new_callable=AsyncMock)
@patch("mnemo.workers.import_worker._process_db_job", new_callable=AsyncMock)
@patch("mnemo.workers.import_worker._reset_stuck_jobs", new_callable=AsyncMock)
@patch("mnemo.workers.import_worker.AsyncSessionLocal")
async def test_run_worker_main_loop(
    mock_session_local,
    mock_reset,
    mock_process_db,
    mock_process_redis,
    mock_sleep,
    mock_db_session,
):
    mock_session_local.return_value.__aenter__.return_value = mock_db_session

    # Simulate a few iterations of the loop
    # 1. Redis job succeeds
    # 2. Redis fails, DB job succeeds
    # 3. Both fail, worker sleeps
    # 4. An exception occurs
    # 5. Loop breaks
    mock_process_redis.side_effect = [True, False, False, False, asyncio.CancelledError]
    mock_process_db.side_effect = [True, False, Exception("DB error")]

    with pytest.raises(asyncio.CancelledError):
        await run_worker()

    assert mock_reset.call_count == 1
    assert mock_process_redis.call_count == 5
    assert mock_process_db.call_count == 3
    assert mock_sleep.call_count == 2  # Once for no jobs, once for the error
    mock_sleep.assert_any_call(1.0)
