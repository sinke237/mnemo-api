"""
CSV import worker.
Consumes import jobs asynchronously and processes them into cards.
"""

from __future__ import annotations

import asyncio

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.core.constants import ImportJobStatus
from mnemo.db.database import AsyncSessionLocal
from mnemo.db.redis import WORKER_HEARTBEAT_KEY, WORKER_HEARTBEAT_TTL, get_redis
from mnemo.models.deck import Deck  # noqa: F401 - Register Deck model with Base
from mnemo.models.import_job import ImportJob
from mnemo.models.user import User  # noqa: F401 - Register User model with Base
from mnemo.services import import_job as import_service

logger = structlog.get_logger()


async def _reset_stuck_jobs(db: AsyncSession) -> None:
    stmt = select(ImportJob).where(ImportJob.status == ImportJobStatus.PROCESSING.value)
    result = await db.execute(stmt)
    jobs = result.scalars().all()
    for job in jobs:
        job.status = ImportJobStatus.QUEUED.value
    if jobs:
        await db.flush()


async def _dequeue_job_id() -> str | None:
    try:
        redis = get_redis()
        payload = await redis.blpop(import_service.IMPORT_QUEUE_KEY, timeout=5)
        if payload:
            _, job_id_or_bytes = payload
            job_id: str | None = None
            if isinstance(job_id_or_bytes, bytes):
                job_id = job_id_or_bytes.decode("utf-8")
            else:
                job_id = job_id_or_bytes
            return job_id
    except Exception as exc:
        logger.error("import_queue_error", error=str(exc))
    return None


async def _claim_db_job(db: AsyncSession) -> ImportJob | None:
    stmt = (
        select(ImportJob)
        .where(ImportJob.status == ImportJobStatus.QUEUED.value)
        .order_by(ImportJob.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    return job


async def _process_job(
    db: AsyncSession, job_id: str, job: ImportJob | None = None
) -> tuple[bool, bool]:
    """
    Processes a job.
    Returns a tuple of (processed_successfully, is_retriable).
    """
    if not job:
        job = await db.get(ImportJob, job_id, with_for_update=True, populate_existing=True)

    if not job or job.status != ImportJobStatus.QUEUED.value:
        return False, False  # Not successful, not retriable

    # Start a background periodic heartbeat while the job is processing so
    # the worker doesn't appear dead during long-running imports.
    heartbeat_interval = max(int(WORKER_HEARTBEAT_TTL / 2), 1)

    async def _periodic_heartbeat(interval: int) -> None:
        # Keep the loop running even if individual heartbeat writes or sleeps
        # fail transiently. Propagate CancelledError so task cancellation
        # still works as expected.
        while True:
            try:
                await _write_heartbeat()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(
                    "import_worker_periodic_heartbeat_write_failed",
                    error=str(exc),
                    exc_info=True,
                )

            try:
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(
                    "import_worker_periodic_heartbeat_sleep_failed",
                    error=str(exc),
                    exc_info=True,
                )

    heartbeat_task: asyncio.Task[None] | None = None
    try:
        heartbeat_task = asyncio.create_task(_periodic_heartbeat(heartbeat_interval))
        result_job = await import_service.process_import_job(db, job_id)
    finally:
        if heartbeat_task is not None:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                logger.warning("import_worker_heartbeat_cancel_failed", error=str(exc))

    if result_job and result_job.status in {
        ImportJobStatus.COMPLETED.value,
        ImportJobStatus.FAILED.value,
    }:
        await db.commit()
        return True, False  # Successful, not retriable
    else:
        await db.rollback()
        return False, True  # Not successful, but retriable


async def _requeue_job_id(job_id: str) -> bool:
    try:
        redis = get_redis()
        await redis.rpush(import_service.IMPORT_QUEUE_KEY, job_id)
        return True
    except Exception as exc:
        logger.error("import_requeue_error", error=str(exc), job_id=job_id)
        return False


async def _process_redis_job() -> bool:
    job_id = await _dequeue_job_id()
    if job_id:
        processed_successfully, is_retriable = False, False
        try:
            async with AsyncSessionLocal() as db:
                processed_successfully, is_retriable = await _process_job(db, job_id)

            if is_retriable:
                if await _requeue_job_id(job_id):
                    logger.warning("import_job_failed_requeued", job_id=job_id)

            return processed_successfully
        except Exception as exc:
            logger.error("import_job_exception", error=str(exc), job_id=job_id)
            await _requeue_job_id(job_id)
            return False
    return False


async def _process_db_job() -> bool:
    async with AsyncSessionLocal() as db:
        claimed_job = await _claim_db_job(db)
        if claimed_job:
            processed_successfully, _ = await _process_job(db, str(claimed_job.id), job=claimed_job)
            return processed_successfully
    return False


async def _write_heartbeat() -> None:
    try:
        redis = get_redis()
        await redis.set(WORKER_HEARTBEAT_KEY, "1", ex=WORKER_HEARTBEAT_TTL)
    except Exception as exc:
        logger.warning("import_worker_heartbeat_failed", error=str(exc))


async def run_worker(poll_interval: float = 1.0) -> None:
    logger.info("import_worker_starting")
    async with AsyncSessionLocal() as db:
        await _reset_stuck_jobs(db)
        await db.commit()

    while True:
        try:
            await _write_heartbeat()
            if await _process_redis_job():
                continue

            if not await _process_db_job():
                await asyncio.sleep(poll_interval)
        except Exception as exc:
            logger.error("import_worker_failed", error=str(exc))
            await asyncio.sleep(poll_interval)


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
