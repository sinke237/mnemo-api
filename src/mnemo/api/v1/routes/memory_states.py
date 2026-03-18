"""
API endpoints for card memory states, due cards, and weak spots.
"""

from datetime import datetime

import pytz
from fastapi import APIRouter, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.api.dependencies import current_user_dep, db_dep
from mnemo.core.constants import ErrorCode, HTTPStatusCode
from mnemo.models.user import User
from mnemo.schemas.memory_state import (
    AnswerRequest,
    CardMemoryStateResponse,
    DueCardListResponse,
    WeakSpotListResponse,
)
from mnemo.services.spaced_repetition import (
    get_due_cards,
    get_or_create_memory_state,
    get_weak_spots,
    update_memory_state_after_answer,
)
from mnemo.utils.local_time import to_local_time

router = APIRouter()


@router.get(
    "/cards/{card_id}/memory",
    response_model=CardMemoryStateResponse,
    status_code=HTTPStatusCode.OK,
)
async def get_card_memory_state(
    card_id: str,
    db: AsyncSession = db_dep,
    current_user: User = current_user_dep,
) -> CardMemoryStateResponse:
    """Get the current memory state for a user and card pair."""
    memory_state = await get_or_create_memory_state(db, card_id=card_id, user_id=current_user.id)
    if not memory_state:
        raise HTTPException(
            status_code=HTTPStatusCode.NOT_FOUND,
            detail=ErrorCode.CARD_NOT_FOUND,
        )

    due_at_local = (
        to_local_time(memory_state.due_at, current_user.timezone) if memory_state.due_at else None
    )
    response = CardMemoryStateResponse.from_orm(memory_state)
    response.due_at_local = due_at_local
    return response


@router.post(
    "/cards/{card_id}/answer",
    response_model=CardMemoryStateResponse,
    status_code=HTTPStatusCode.OK,
)
async def answer_card(
    card_id: str,
    answer: AnswerRequest,
    db: AsyncSession = db_dep,
    current_user: User = current_user_dep,
) -> CardMemoryStateResponse:
    """Submit an answer for a card and update its memory state."""
    memory_state = await get_or_create_memory_state(db, card_id=card_id, user_id=current_user.id)
    if not memory_state:
        raise HTTPException(
            status_code=HTTPStatusCode.NOT_FOUND,
            detail=ErrorCode.CARD_NOT_FOUND,
        )

    updated_state = update_memory_state_after_answer(memory_state, answer.score)

    due_at_local = (
        to_local_time(updated_state.due_at, current_user.timezone) if updated_state.due_at else None
    )
    response = CardMemoryStateResponse.from_orm(updated_state)
    response.due_at_local = due_at_local

    return response


@router.get(
    "/users/{user_id}/due",
    response_model=DueCardListResponse,
    status_code=HTTPStatusCode.OK,
)
async def get_due_cards_for_user(
    user_id: str,
    db: AsyncSession = db_dep,
    current_user: User = current_user_dep,
) -> DueCardListResponse:
    """Get all cards due today for a user, sorted by urgency."""
    if current_user.id != user_id:
        raise HTTPException(
            status_code=HTTPStatusCode.FORBIDDEN,
            detail="Cannot access another user's due cards.",
        )

    due_cards = await get_due_cards(db, current_user)

    response_cards = []
    for memory_state, flashcard in due_cards:
        due_at_local = (
            to_local_time(memory_state.due_at, current_user.timezone)
            if memory_state.due_at
            else None
        )
        overdue_by = (
            str(datetime.now(pytz.utc) - memory_state.due_at) if memory_state.due_at else None
        )
        card_data = {
            "id": flashcard.id,
            "deck_id": flashcard.deck_id,
            "question": flashcard.question,
            "due_at": memory_state.due_at,
            "due_at_local": due_at_local,
            "overdue_by": overdue_by,
            "ease_factor": memory_state.ease_factor,
        }
        response_cards.append(card_data)

    return DueCardListResponse(due_count=len(response_cards), cards=response_cards)


@router.get(
    "/users/{user_id}/weak-spots",
    response_model=WeakSpotListResponse,
    status_code=HTTPStatusCode.OK,
)
async def get_weak_spots_for_user(
    user_id: str,
    limit: int = 10,
    db: AsyncSession = db_dep,
    current_user: User = current_user_dep,
) -> WeakSpotListResponse:
    """Get the cards with the lowest ease factor for a user."""
    if current_user.id != user_id:
        raise HTTPException(
            status_code=HTTPStatusCode.FORBIDDEN,
            detail="Cannot access another user's weak spots.",
        )

    weak_spots = await get_weak_spots(db, current_user, limit)

    response_cards = []
    for memory_state, flashcard in weak_spots:
        card_data = {
            "id": flashcard.id,
            "deck_id": flashcard.deck_id,
            "question": flashcard.question,
            "ease_factor": memory_state.ease_factor,
            "last_score": memory_state.last_score,
            "repetitions": memory_state.repetitions,
        }
        response_cards.append(card_data)

    return WeakSpotListResponse(count=len(response_cards), cards=response_cards)
