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
from mnemo.db.redis import get_redis
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


async def run_worker(poll_interval: float = 1.0) -> None:
    logger.info("import_worker_starting")
    async with AsyncSessionLocal() as db:
        await _reset_stuck_jobs(db)
        await db.commit()

    while True:
        try:
            job_id = await _dequeue_job_id()
            if job_id:
                async with AsyncSessionLocal() as db:
                    job = await db.get(ImportJob, job_id, with_for_update=True)
                    if job and job.status == ImportJobStatus.QUEUED.value:
                        await import_service.process_import_job(db, job_id)
                        await db.commit()
                continue

            # Check if there are any queued jobs before opening a transaction
            async with AsyncSessionLocal() as db:
                check_stmt = (
                    select(ImportJob.id)
                    .where(ImportJob.status == ImportJobStatus.QUEUED.value)
                    .limit(1)
                )
                check_res = await db.execute(check_stmt)
                has_queued = check_res.scalar_one_or_none() is not None

            if has_queued:
                job_processed = False
                async with AsyncSessionLocal() as db:
                    claimed_job = await _claim_db_job(db)
                    if claimed_job:
                        await import_service.process_import_job(db, str(claimed_job.id))
                        await db.commit()
                        job_processed = True

                if not job_processed:
                    await asyncio.sleep(poll_interval)
            else:
                await asyncio.sleep(poll_interval)
        except Exception as exc:
            logger.error("import_worker_failed", error=str(exc))
            await asyncio.sleep(poll_interval)


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
