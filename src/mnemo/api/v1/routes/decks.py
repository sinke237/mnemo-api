"""
Deck routes.
Implements deck CRUD and deck card listing.
Per spec section 06: Decks.
"""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, Header, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.api.dependencies import get_current_user_from_token, require_user_scope
from mnemo.api.utils import _error_response
from mnemo.core.constants import MAX_PAGE_SIZE, ErrorCode, PermissionScope
from mnemo.core.exceptions import DeckNameConflictError, DeckNotFoundError
from mnemo.db.database import get_db
from mnemo.models.user import User
from mnemo.schemas.deck import (
    DeckCreate,
    DeckListItem,
    DeckListResponse,
    DeckReplace,
    DeckResponse,
    DeckUpdate,
)
from mnemo.schemas.error import ErrorResponse
from mnemo.schemas.flashcard import FlashcardListResponse, FlashcardResponse
from mnemo.services import deck as deck_service
from mnemo.services import flashcard as flashcard_service
from mnemo.services import idempotency as idempotency_service

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/decks", tags=["decks"])
# module-level Depends singletons to satisfy ruff B008
_db_dep = Depends(get_db)
_current_user_dep = Depends(get_current_user_from_token)


def _deck_not_found(deck_id: str | None, resource_name: str | None = None) -> JSONResponse:
    return _error_response(
        ErrorCode.DECK_NOT_FOUND,
        "Deck not found.",
        404,
        resource_type="deck",
        resource_id=deck_id,
        resource_name=resource_name,
    )


@router.get(
    "",
    dependencies=[Depends(require_user_scope(PermissionScope.DECKS_READ))],
    response_model=DeckListResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="List decks",
)
async def list_decks(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    tag: str | None = None,
    sort: Literal["created_at", "updated_at", "name"] = "created_at",
    order: Literal["asc", "desc"] = "desc",
    current_user: User = _current_user_dep,
    db: AsyncSession = _db_dep,
) -> DeckListResponse:
    decks, pagination = await deck_service.list_decks(
        db,
        user_id=current_user.id,
        page=page,
        per_page=per_page,
        tag=tag,
        sort=sort,
        order=order,
    )
    return DeckListResponse(
        data=[DeckListItem.model_validate(deck) for deck in decks],
        pagination=pagination,
    )


@router.post(
    "",
    status_code=201,
    response_model=DeckResponse,
    dependencies=[Depends(require_user_scope(PermissionScope.DECKS_WRITE))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        409: {"model": ErrorResponse, "description": "Deck name conflict"},
    },
    summary="Create deck",
)
async def create_deck(
    deck_data: DeckCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: User = _current_user_dep,
    db: AsyncSession = _db_dep,
) -> DeckResponse | JSONResponse:
    endpoint = "POST /v1/decks"
    if idempotency_key:
        record = await idempotency_service.get_idempotency_record(
            db, current_user.id, endpoint, idempotency_key
        )
        if record is not None:
            return JSONResponse(status_code=record.status_code, content=record.response_body)

    try:
        deck = await deck_service.create_deck(
            db,
            user_id=current_user.id,
            name=deck_data.name,
            description=deck_data.description,
            tags=deck_data.tags or [],
        )
    except DeckNameConflictError as exc:
        return _error_response(ErrorCode.DECK_NAME_CONFLICT, str(exc), 409)

    response = DeckResponse.model_validate(deck)

    if idempotency_key:
        await idempotency_service.store_idempotency_record(
            db,
            user_id=current_user.id,
            endpoint=endpoint,
            key=idempotency_key,
            status_code=201,
            response_body=response.model_dump(mode="json"),
        )

    return response


@router.get(
    "/{deck_id}",
    response_model=DeckResponse,
    dependencies=[Depends(require_user_scope(PermissionScope.DECKS_READ))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Get deck",
)
async def get_deck(
    deck_id: str,
    current_user: User = _current_user_dep,
    db: AsyncSession = _db_dep,
) -> DeckResponse | JSONResponse:
    deck = await deck_service.get_deck_by_id(db, current_user.id, deck_id)
    if deck is None:
        return _deck_not_found(deck_id)
    return DeckResponse.model_validate(deck)


@router.put(
    "/{deck_id}",
    response_model=DeckResponse,
    dependencies=[Depends(require_user_scope(PermissionScope.DECKS_WRITE))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
    summary="Replace deck",
)
async def replace_deck(
    deck_id: str,
    deck_data: DeckReplace,
    current_user: User = _current_user_dep,
    db: AsyncSession = _db_dep,
) -> DeckResponse | JSONResponse:
    try:
        deck = await deck_service.update_deck(
            db,
            user_id=current_user.id,
            deck_id=deck_id,
            name=deck_data.name,
            description=deck_data.description,
            tags=deck_data.tags,
        )
    except DeckNotFoundError as exc:
        return _deck_not_found(
            getattr(exc, "deck_id", deck_id), getattr(exc, "resource_name", None)
        )
    except DeckNameConflictError as exc:
        return _error_response(ErrorCode.DECK_NAME_CONFLICT, str(exc), 409)

    return DeckResponse.model_validate(deck)


@router.patch(
    "/{deck_id}",
    response_model=DeckResponse,
    dependencies=[Depends(require_user_scope(PermissionScope.DECKS_WRITE))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
    summary="Update deck",
)
async def update_deck(
    deck_id: str,
    deck_data: DeckUpdate,
    current_user: User = _current_user_dep,
    db: AsyncSession = _db_dep,
) -> DeckResponse | JSONResponse:
    try:
        deck = await deck_service.update_deck(
            db,
            user_id=current_user.id,
            deck_id=deck_id,
            name=deck_data.name,
            description=deck_data.description,
            tags=deck_data.tags,
        )
    except DeckNotFoundError as exc:
        return _deck_not_found(
            getattr(exc, "deck_id", deck_id), getattr(exc, "resource_name", None)
        )
    except DeckNameConflictError as exc:
        return _error_response(ErrorCode.DECK_NAME_CONFLICT, str(exc), 409)

    return DeckResponse.model_validate(deck)


@router.delete(
    "/{deck_id}",
    status_code=200,
    response_model=None,
    dependencies=[Depends(require_user_scope(PermissionScope.DECKS_WRITE))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Delete deck",
)
async def delete_deck(
    deck_id: str,
    current_user: User = _current_user_dep,
    db: AsyncSession = _db_dep,
) -> Response | JSONResponse:
    try:
        await deck_service.delete_deck(db, current_user.id, deck_id)
    except DeckNotFoundError as exc:
        return _deck_not_found(
            getattr(exc, "deck_id", deck_id), getattr(exc, "resource_name", None)
        )
    return Response(status_code=200)


@router.get(
    "/{deck_id}/cards",
    response_model=FlashcardListResponse,
    dependencies=[Depends(require_user_scope(PermissionScope.DECKS_READ))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="List cards in a deck",
)
async def list_cards_for_deck(
    deck_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    current_user: User = _current_user_dep,
    db: AsyncSession = _db_dep,
) -> FlashcardListResponse | JSONResponse:
    try:
        cards, pagination = await flashcard_service.list_cards_for_deck(
            db,
            user_id=current_user.id,
            deck_id=deck_id,
            page=page,
            per_page=per_page,
        )
    except DeckNotFoundError as exc:
        return _deck_not_found(
            getattr(exc, "deck_id", deck_id), getattr(exc, "resource_name", None)
        )

    return FlashcardListResponse(
        data=[FlashcardResponse.model_validate(card) for card in cards],
        pagination=pagination,
    )
