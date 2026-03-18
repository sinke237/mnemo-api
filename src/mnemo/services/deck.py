"""
Deck service.
Handles deck CRUD, versioning, and pagination.
Per spec section 06 and FR-02.*.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import ColumnElement

from mnemo.core.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from mnemo.core.exceptions import DeckNameConflictError, DeckNotFoundError
from mnemo.models.card_memory_state import CardMemoryState
from mnemo.models.deck import Deck
from mnemo.models.flashcard import Flashcard
from mnemo.services.utils import pagination_meta
from mnemo.utils.id_generator import generate_deck_id


async def _deck_name_exists(
    db: AsyncSession,
    user_id: str,
    name: str,
    exclude_deck_id: str | None = None,
) -> bool:
    stmt = select(Deck.id).where(Deck.user_id == user_id, func.lower(Deck.name) == func.lower(name))
    if exclude_deck_id is not None:
        stmt = stmt.where(Deck.id != exclude_deck_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None


async def create_deck(
    db: AsyncSession,
    user_id: str,
    name: str,
    description: str | None,
    tags: list[str],
) -> Deck:
    """Create a new deck for a user."""
    if await _deck_name_exists(db, user_id, name):
        raise DeckNameConflictError(f"Deck name already exists: {name}")

    deck = Deck(
        id=generate_deck_id(),
        user_id=user_id,
        name=name,
        description=description,
        tags=tags,
        card_count=0,
        version=1,
    )
    db.add(deck)
    try:
        await db.flush()
    except IntegrityError as err:
        await db.rollback()
        raise DeckNameConflictError(f"Deck name already exists: {name}") from err
    await db.refresh(deck)
    return deck


async def get_deck_by_id(db: AsyncSession, user_id: str, deck_id: str) -> Deck | None:
    stmt = select(Deck).where(Deck.id == deck_id, Deck.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_decks(
    db: AsyncSession,
    user_id: str,
    page: int = 1,
    per_page: int = DEFAULT_PAGE_SIZE,
    tag: str | None = None,
    sort: str = "created_at",
    order: str = "desc",
) -> tuple[Sequence[Deck], dict[str, int]]:
    """Return paginated list of decks for a user."""
    page = max(page, 1)
    per_page = min(max(per_page, 1), MAX_PAGE_SIZE)

    filters: list[ColumnElement[bool]] = [Deck.user_id == user_id]
    if tag:
        filters.append(Deck.tags.contains([tag]))

    sort_map = {
        "name": Deck.name,
        "created_at": Deck.created_at,
        "updated_at": Deck.updated_at,
    }
    sort_col = sort_map.get(sort, Deck.created_at)
    order_clause = sort_col.asc() if order == "asc" else sort_col.desc()

    count_stmt = select(func.count()).select_from(Deck).where(*filters)
    total = await db.scalar(count_stmt)
    total = int(total or 0)

    stmt: Select[Deck] = (
        select(Deck)
        .where(*filters)
        .order_by(order_clause)
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(stmt)
    decks = result.scalars().all()

    return decks, pagination_meta(page, per_page, total)


async def update_deck(
    db: AsyncSession,
    user_id: str,
    deck_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
) -> Deck:
    deck = await get_deck_by_id(db, user_id, deck_id)
    if deck is None:
        raise DeckNotFoundError(f"Deck not found: {deck_id}")

    changed = False

    if name is not None and name != deck.name:
        if await _deck_name_exists(db, user_id, name, exclude_deck_id=deck_id):
            raise DeckNameConflictError(f"Deck name already exists: {name}")
        deck.name = name
        changed = True

    if description is not None and description != deck.description:
        deck.description = description
        changed = True

    if tags is not None and tags != deck.tags:
        deck.tags = tags
        changed = True

    if changed:
        deck.version += 1

    try:
        await db.flush()
    except IntegrityError as err:
        await db.rollback()
        raise DeckNameConflictError(f"Deck name already exists: {name}") from err
    await db.refresh(deck)
    return deck


async def delete_deck(db: AsyncSession, user_id: str, deck_id: str) -> None:
    deck = await get_deck_by_id(db, user_id, deck_id)
    if deck is None:
        raise DeckNotFoundError(f"Deck not found: {deck_id}")

    card_ids = await db.execute(select(Flashcard.id).where(Flashcard.deck_id == deck.id))
    card_id_list = card_ids.scalars().all()

    if card_id_list:
        await db.execute(delete(CardMemoryState).where(CardMemoryState.card_id.in_(card_id_list)))
        await db.execute(delete(Flashcard).where(Flashcard.id.in_(card_id_list)))

    await db.delete(deck)
    await db.flush()
