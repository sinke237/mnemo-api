"""
Flashcard service.
Handles card CRUD and deck versioning.
Per spec section 07 and FR-02.*.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import ceil

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from mnemo.core.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from mnemo.core.exceptions import CardNotFoundError, DeckNotFoundError
from mnemo.models.card_memory_state import CardMemoryState
from mnemo.models.deck import Deck
from mnemo.models.flashcard import Flashcard
from mnemo.utils.id_generator import generate_card_id


def _pagination_meta(page: int, per_page: int, total: int) -> dict[str, int]:
    total_pages = ceil(total / per_page) if per_page else 0
    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
    }


async def _get_deck(db: AsyncSession, user_id: str, deck_id: str) -> Deck | None:
    result = await db.execute(select(Deck).where(Deck.id == deck_id, Deck.user_id == user_id))
    return result.scalar_one_or_none()


async def create_card(
    db: AsyncSession,
    user_id: str,
    deck_id: str,
    *,
    question: str,
    answer: str,
    source_ref: str | None,
    tags: list[str],
    difficulty: int,
) -> Flashcard:
    deck = await _get_deck(db, user_id, deck_id)
    if deck is None:
        raise DeckNotFoundError(f"Deck not found: {deck_id}")

    card = Flashcard(
        id=generate_card_id(),
        deck_id=deck_id,
        question=question,
        answer=answer,
        source_ref=source_ref,
        tags=tags,
        difficulty=difficulty,
    )
    db.add(card)

    deck.card_count += 1
    deck.version += 1

    await db.flush()
    await db.refresh(card)
    return card


async def get_card_by_id(db: AsyncSession, user_id: str, card_id: str) -> Flashcard | None:
    stmt = (
        select(Flashcard)
        .join(Deck, Deck.id == Flashcard.deck_id)
        .where(Flashcard.id == card_id, Deck.user_id == user_id)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_cards_for_deck(
    db: AsyncSession,
    user_id: str,
    deck_id: str,
    page: int = 1,
    per_page: int = DEFAULT_PAGE_SIZE,
) -> tuple[Sequence[Flashcard], dict[str, int]]:
    deck = await _get_deck(db, user_id, deck_id)
    if deck is None:
        raise DeckNotFoundError(f"Deck not found: {deck_id}")

    page = max(page, 1)
    per_page = min(max(per_page, 1), MAX_PAGE_SIZE)

    count_stmt = select(func.count()).select_from(Flashcard).where(Flashcard.deck_id == deck_id)
    total = await db.scalar(count_stmt)
    total = int(total or 0)

    stmt: Select[Flashcard] = (
        select(Flashcard)
        .where(Flashcard.deck_id == deck_id)
        .order_by(Flashcard.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(stmt)
    cards = result.scalars().all()

    return cards, _pagination_meta(page, per_page, total)


async def update_card(
    db: AsyncSession,
    user_id: str,
    card_id: str,
    *,
    question: str | None = None,
    answer: str | None = None,
    source_ref: str | None = None,
    tags: list[str] | None = None,
    difficulty: int | None = None,
) -> Flashcard:
    card = await get_card_by_id(db, user_id, card_id)
    if card is None:
        raise CardNotFoundError(f"Card not found: {card_id}")

    deck = await _get_deck(db, user_id, card.deck_id)
    if deck is None:
        raise DeckNotFoundError(f"Deck not found: {card.deck_id}")

    changed = False

    if question is not None and question != card.question:
        card.question = question
        changed = True

    if answer is not None and answer != card.answer:
        card.answer = answer
        changed = True

    if source_ref is not None and source_ref != card.source_ref:
        card.source_ref = source_ref
        changed = True

    if tags is not None and tags != card.tags:
        card.tags = tags
        changed = True

    if difficulty is not None and difficulty != card.difficulty:
        card.difficulty = difficulty
        changed = True

    if changed:
        deck.version += 1

    await db.flush()
    await db.refresh(card)
    return card


async def delete_card(db: AsyncSession, user_id: str, card_id: str) -> None:
    card = await get_card_by_id(db, user_id, card_id)
    if card is None:
        raise CardNotFoundError(f"Card not found: {card_id}")

    deck = await _get_deck(db, user_id, card.deck_id)
    if deck is None:
        raise DeckNotFoundError(f"Deck not found: {card.deck_id}")

    await db.execute(delete(CardMemoryState).where(CardMemoryState.card_id == card.id))
    await db.delete(card)

    deck.card_count = max(deck.card_count - 1, 0)
    deck.version += 1

    await db.flush()
