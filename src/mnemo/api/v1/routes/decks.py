"""
Deck routes.
Implements deck CRUD and deck card listing.
Per spec section 06: Decks.
"""

from fastapi import APIRouter, Depends, Header, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.api.dependencies import get_current_user_from_token, require_user_scope
from mnemo.core.constants import ErrorCode, PermissionScope
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

router = APIRouter(prefix="/decks", tags=["decks"])
# module-level Depends singletons to satisfy ruff B008
_db_dep = Depends(get_db)
_current_user_dep = Depends(get_current_user_from_token)


def _error_response(code: ErrorCode, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code.value,
                "message": message,
                "status": status_code,
            }
        },
    )


@router.get(
    "",
    dependencies=[Depends(require_user_scope(PermissionScope.DECKS_READ))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="List decks",
)
async def list_decks(
    page: int = 1,
    per_page: int = 20,
    tag: str | None = None,
    sort: str = "created_at",
    order: str = "desc",
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
) -> DeckResponse:
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
) -> DeckResponse:
    deck = await deck_service.get_deck_by_id(db, current_user.id, deck_id)
    if deck is None:
        return _error_response(ErrorCode.DECK_NOT_FOUND, f"No deck found with ID {deck_id}.", 404)
    return DeckResponse.model_validate(deck)


@router.put(
    "/{deck_id}",
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
) -> DeckResponse:
    try:
        deck = await deck_service.update_deck(
            db,
            user_id=current_user.id,
            deck_id=deck_id,
            name=deck_data.name,
            description=deck_data.description,
            tags=deck_data.tags,
        )
    except DeckNotFoundError:
        return _error_response(ErrorCode.DECK_NOT_FOUND, f"No deck found with ID {deck_id}.", 404)
    except DeckNameConflictError as exc:
        return _error_response(ErrorCode.DECK_NAME_CONFLICT, str(exc), 409)

    return DeckResponse.model_validate(deck)


@router.patch(
    "/{deck_id}",
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
) -> DeckResponse:
    try:
        deck = await deck_service.update_deck(
            db,
            user_id=current_user.id,
            deck_id=deck_id,
            name=deck_data.name,
            description=deck_data.description,
            tags=deck_data.tags,
        )
    except DeckNotFoundError:
        return _error_response(ErrorCode.DECK_NOT_FOUND, f"No deck found with ID {deck_id}.", 404)
    except DeckNameConflictError as exc:
        return _error_response(ErrorCode.DECK_NAME_CONFLICT, str(exc), 409)

    return DeckResponse.model_validate(deck)


@router.delete(
    "/{deck_id}",
    status_code=204,
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
) -> Response:
    try:
        await deck_service.delete_deck(db, current_user.id, deck_id)
    except DeckNotFoundError:
        return _error_response(ErrorCode.DECK_NOT_FOUND, f"No deck found with ID {deck_id}.", 404)
    return Response(status_code=204)


@router.get(
    "/{deck_id}/cards",
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
    page: int = 1,
    per_page: int = 20,
    current_user: User = _current_user_dep,
    db: AsyncSession = _db_dep,
) -> FlashcardListResponse:
    try:
        cards, pagination = await flashcard_service.list_cards_for_deck(
            db,
            user_id=current_user.id,
            deck_id=deck_id,
            page=page,
            per_page=per_page,
        )
    except DeckNotFoundError:
        return _error_response(ErrorCode.DECK_NOT_FOUND, f"No deck found with ID {deck_id}.", 404)

    return FlashcardListResponse(
        data=[FlashcardResponse.model_validate(card) for card in cards],
        pagination=pagination,
    )
