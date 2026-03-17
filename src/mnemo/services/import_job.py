"""
Import job service.
Handles CSV import job creation, parsing, and processing.
Per spec section 10: CSV Import and FR-01.*.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from datetime import UTC, datetime
from io import StringIO

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.core.constants import DEFAULT_DIFFICULTY, ImportJobStatus, ImportMode
from mnemo.db.redis import get_redis
from mnemo.models.card_memory_state import CardMemoryState
from mnemo.models.deck import Deck
from mnemo.models.flashcard import Flashcard
from mnemo.models.import_job import ImportJob
from mnemo.utils.id_generator import generate_card_id, generate_import_job_id

IMPORT_QUEUE_KEY = "mnemo:import:queue"


def _is_header_row(row: list[str]) -> bool:
    if len(row) < 2:
        return False
    first = row[0].strip().lower()
    second = row[1].strip().lower()
    # Only match if the cells are exactly "question" and "answer", not if they contain those words
    return first == "question" and second == "answer"


def _normalize_pair(question: str, answer: str) -> tuple[str, str]:
    return (question.strip().lower(), answer.strip().lower())


def _parse_csv_rows(text: str) -> tuple[list[tuple[str, str]], list[str]]:
    sniffer = csv.Sniffer()
    dialect: type[csv.Dialect] | str = "excel"
    try:
        dialect = sniffer.sniff(text, delimiters=",;\t")
    except csv.Error:
        pass  # Keep default dialect

    reader = csv.reader(StringIO(text), dialect)
    rows: list[tuple[str, str]] = []
    errors: list[str] = []

    # Check if first row is actually a header by looking at its content
    first_row = None
    try:
        first_row = next(reader)
    except StopIteration:
        return [], ["CSV file is empty."]

    skip_first = _is_header_row(first_row) if first_row else False

    # If first row is not a header, process it as data
    if not skip_first and first_row:
        if not first_row or all(not cell.strip() for cell in first_row):
            pass  # Skip empty row
        elif len(first_row) < 2:
            errors.append("Row 1 has fewer than 2 columns.")
        else:
            question = first_row[0].strip()
            answer = first_row[1].strip()
            if question and answer:
                rows.append((question, answer))
            else:
                errors.append("Row 1 has blank question or answer.")

    # Process remaining rows
    for idx, row in enumerate(reader, start=2):
        if not row or all(not cell.strip() for cell in row):
            continue

        if len(row) < 2:
            errors.append(f"Row {idx} has fewer than 2 columns.")
            continue

        question = row[0].strip()
        answer = row[1].strip()
        if not question or not answer:
            errors.append(f"Row {idx} has blank question or answer.")
            continue

        rows.append((question, answer))

    return rows, errors


async def create_import_job(
    db: AsyncSession,
    *,
    user_id: str,
    deck_id: str,
    mode: ImportMode,
    file_text: str,
    original_filename: str | None,
) -> ImportJob:
    job = ImportJob(
        id=generate_import_job_id(),
        user_id=user_id,
        deck_id=deck_id,
        status=ImportJobStatus.QUEUED.value,
        mode=mode.value,
        file_text=file_text,
        original_filename=original_filename,
        cards_imported=0,
        cards_skipped=0,
        errors=[],
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)
    return job


async def enqueue_import_job(job_id: str) -> bool:
    """Push a job ID onto the import queue. Returns False if Redis is unavailable."""
    try:
        redis = get_redis()
        await redis.rpush(IMPORT_QUEUE_KEY, job_id)
        return True
    except Exception:
        return False


async def get_import_job(db: AsyncSession, *, user_id: str, job_id: str) -> ImportJob | None:
    stmt = select(ImportJob).where(ImportJob.id == job_id, ImportJob.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _get_deck(db: AsyncSession, user_id: str, deck_id: str) -> Deck | None:
    stmt = select(Deck).where(Deck.id == deck_id, Deck.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _fetch_existing_pairs(db: AsyncSession, deck_id: str) -> set[tuple[str, str]]:
    stmt = select(Flashcard.question, Flashcard.answer).where(Flashcard.deck_id == deck_id)
    result = await db.execute(stmt)
    pairs = result.all()
    return {_normalize_pair(question, answer) for question, answer in pairs}


def _dedupe_rows(
    rows: Iterable[tuple[str, str]],
    existing_pairs: set[tuple[str, str]],
) -> tuple[list[tuple[str, str]], int]:
    unique_rows: list[tuple[str, str]] = []
    skipped = 0
    seen: set[tuple[str, str]] = set(existing_pairs)

    for question, answer in rows:
        key = _normalize_pair(question, answer)
        if key in seen:
            skipped += 1
            continue
        seen.add(key)
        unique_rows.append((question, answer))

    return unique_rows, skipped


async def _wipe_deck_cards(db: AsyncSession, deck_id: str) -> int:
    card_ids = await db.execute(select(Flashcard.id).where(Flashcard.deck_id == deck_id))
    card_id_list = card_ids.scalars().all()
    if card_id_list:
        await db.execute(delete(CardMemoryState).where(CardMemoryState.card_id.in_(card_id_list)))
        await db.execute(delete(Flashcard).where(Flashcard.id.in_(card_id_list)))
    return len(card_id_list)


async def process_import_job(db: AsyncSession, job_id: str) -> ImportJob | None:
    job = await db.get(ImportJob, job_id)
    if job is None:
        return None

    if job.status not in {ImportJobStatus.QUEUED.value, ImportJobStatus.PROCESSING.value}:
        return job

    job.status = ImportJobStatus.PROCESSING.value
    await db.flush()

    cards_added = 0
    try:
        deck = await _get_deck(db, job.user_id, job.deck_id)
        if deck is None:
            raise ValueError("Deck not found for import job.")

        rows, parse_errors = _parse_csv_rows(job.file_text)
        job.errors = parse_errors

        if not rows:
            if parse_errors:
                raise ValueError(", ".join(parse_errors))
            raise ValueError("No valid rows found in CSV.")

        skipped = 0
        if job.mode == ImportMode.REPLACE.value:
            deleted_count = await _wipe_deck_cards(db, deck.id)
            deck.card_count = 0
            if deleted_count > 0:
                deck.version += deleted_count
            rows, skipped = _dedupe_rows(rows, set())
        else:  # Merge mode
            existing_pairs = await _fetch_existing_pairs(db, deck.id)
            rows, skipped = _dedupe_rows(rows, existing_pairs)

        job.cards_skipped = skipped

        if rows:
            new_cards = [
                Flashcard(
                    id=generate_card_id(),
                    deck_id=deck.id,
                    question=question,
                    answer=answer,
                    source_ref=None,
                    tags=[],
                    difficulty=DEFAULT_DIFFICULTY,
                )
                for question, answer in rows
            ]
            db.add_all(new_cards)
            cards_added = len(new_cards)
            deck.card_count += cards_added
            deck.version += cards_added
            if job.original_filename:
                deck.source_file = job.original_filename

        job.status = ImportJobStatus.COMPLETED.value
        job.cards_imported = cards_added
        job.completed_at = datetime.now(UTC)

    except (ValueError, csv.Error) as exc:
        job.status = ImportJobStatus.FAILED.value
        job.errors.append(str(exc))
        job.completed_at = datetime.now(UTC)
    except Exception:
        job.status = ImportJobStatus.FAILED.value
        job.errors.append("An unexpected error occurred during import.")
        job.completed_at = datetime.now(UTC)
        # In a real application, you'd want to log the full exception here.
    finally:
        await db.flush()

    return job
