"""
Flashcard routes.
Implements flashcard CRUD.
Per spec section 07: Flashcards.
"""

from fastapi import APIRouter, Depends, Header, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.api.dependencies import get_current_user_from_token, require_user_scope
from mnemo.api.utils import _error_response
from mnemo.core.constants import DEFAULT_DIFFICULTY, ErrorCode, PermissionScope
from mnemo.core.exceptions import CardNotFoundError, DeckNotFoundError, IdempotencyConflictError
from mnemo.db.database import get_db
from mnemo.models.user import User
from mnemo.schemas.error import ErrorDetail, ErrorResponse
from mnemo.schemas.flashcard import (
    FlashcardCreate,
    FlashcardReplace,
    FlashcardResponse,
    FlashcardUpdate,
)
from mnemo.services import flashcard as flashcard_service
from mnemo.services import idempotency as idempotency_service

router = APIRouter(prefix="", tags=["cards"])
# module-level Depends singletons to satisfy ruff B008
_db_dep = Depends(get_db)
_current_user_dep = Depends(get_current_user_from_token)


def _card_not_found(card_id: str, resource_name: str | None = None) -> JSONResponse:
    return _error_response(
        ErrorCode.CARD_NOT_FOUND,
        "Card not found.",
        404,
        resource_type="card",
        resource_id=card_id,
        resource_name=resource_name,
    )


def _deck_not_found(deck_id: str | None, resource_name: str | None = None) -> JSONResponse:
    return _error_response(
        ErrorCode.DECK_NOT_FOUND,
        "Deck not found.",
        404,
        resource_type="deck",
        resource_id=deck_id,
        resource_name=resource_name,
    )


@router.post(
    "/decks/{deck_id}/cards",
    status_code=201,
    response_model=FlashcardResponse,
    dependencies=[Depends(require_user_scope(PermissionScope.DECKS_WRITE))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Add card to deck",
)
async def create_card(
    deck_id: str,
    card_data: FlashcardCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: User = _current_user_dep,
    db: AsyncSession = _db_dep,
) -> FlashcardResponse | JSONResponse:
    endpoint = f"POST /v1/decks/{deck_id}/cards"
    if idempotency_key:
        try:
            async with db.begin():
                record = await idempotency_service.reserve_idempotency_record(
                    db, current_user.id, endpoint, idempotency_key
                )
                card = await flashcard_service.create_card(
                    db,
                    user_id=current_user.id,
                    deck_id=deck_id,
                    question=card_data.question,
                    answer=card_data.answer,
                    source_ref=card_data.source_ref,
                    tags=card_data.tags or [],
                    difficulty=(
                        card_data.difficulty
                        if card_data.difficulty is not None
                        else DEFAULT_DIFFICULTY
                    ),
                )
                response = FlashcardResponse.model_validate(card)
                idempotency_service.finalize_idempotency_record(
                    record,
                    status_code=201,
                    response_body=response.model_dump(mode="json"),
                )
            return response
        except IdempotencyConflictError:
            existing = await idempotency_service.get_idempotency_record(
                db, current_user.id, endpoint, idempotency_key
            )
            if existing is None:
                error = ErrorResponse(
                    error=ErrorDetail(
                        code=ErrorCode.IDEMPOTENCY_CONFLICT,
                        message="Idempotency key conflict.",
                        status=409,
                    )
                )
                return JSONResponse(status_code=409, content=error.model_dump(mode="json"))
            return JSONResponse(status_code=existing.status_code, content=existing.response_body)
        except DeckNotFoundError as exc:
            return _deck_not_found(
                getattr(exc, "deck_id", deck_id), getattr(exc, "resource_name", None)
            )

    try:
        card = await flashcard_service.create_card(
            db,
            user_id=current_user.id,
            deck_id=deck_id,
            question=card_data.question,
            answer=card_data.answer,
            source_ref=card_data.source_ref,
            tags=card_data.tags or [],
            difficulty=(
                card_data.difficulty if card_data.difficulty is not None else DEFAULT_DIFFICULTY
            ),
        )
    except DeckNotFoundError as exc:
        return _deck_not_found(
            getattr(exc, "deck_id", deck_id), getattr(exc, "resource_name", None)
        )

    return FlashcardResponse.model_validate(card)


@router.get(
    "/cards/{card_id}",
    response_model=FlashcardResponse,
    dependencies=[Depends(require_user_scope(PermissionScope.DECKS_READ))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Get card",
)
async def get_card(
    card_id: str,
    current_user: User = _current_user_dep,
    db: AsyncSession = _db_dep,
) -> FlashcardResponse | JSONResponse:
    card = await flashcard_service.get_card_by_id(db, current_user.id, card_id)
    if card is None:
        return _card_not_found(card_id)
    return FlashcardResponse.model_validate(card)


@router.put(
    "/cards/{card_id}",
    response_model=FlashcardResponse,
    dependencies=[Depends(require_user_scope(PermissionScope.DECKS_WRITE))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Replace card",
)
async def replace_card(
    card_id: str,
    card_data: FlashcardReplace,
    current_user: User = _current_user_dep,
    db: AsyncSession = _db_dep,
) -> FlashcardResponse | JSONResponse:
    try:
        card = await flashcard_service.update_card(
            db,
            user_id=current_user.id,
            card_id=card_id,
            question=card_data.question,
            answer=card_data.answer,
            source_ref=card_data.source_ref,
            source_ref_set=True,
            tags=card_data.tags,
            difficulty=card_data.difficulty,
        )
    except CardNotFoundError as exc:
        return _card_not_found(
            getattr(exc, "card_id", card_id), getattr(exc, "resource_name", None)
        )
    except DeckNotFoundError as exc:
        return _error_response(
            ErrorCode.DECK_NOT_FOUND,
            "Deck not found.",
            404,
            resource_type="deck",
            resource_id=getattr(exc, "deck_id", None),
            resource_name=getattr(exc, "resource_name", None),
        )

    return FlashcardResponse.model_validate(card)


@router.patch(
    "/cards/{card_id}",
    response_model=FlashcardResponse,
    dependencies=[Depends(require_user_scope(PermissionScope.DECKS_WRITE))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Update card",
)
async def update_card(
    card_id: str,
    card_data: FlashcardUpdate,
    current_user: User = _current_user_dep,
    db: AsyncSession = _db_dep,
) -> FlashcardResponse | JSONResponse:
    try:
        card = await flashcard_service.update_card(
            db,
            user_id=current_user.id,
            card_id=card_id,
            question=card_data.question,
            answer=card_data.answer,
            source_ref=card_data.source_ref,
            source_ref_set="source_ref" in card_data.model_fields_set,
            tags=card_data.tags,
            difficulty=card_data.difficulty,
        )
    except CardNotFoundError as exc:
        return _card_not_found(
            getattr(exc, "card_id", card_id), getattr(exc, "resource_name", None)
        )
    except DeckNotFoundError as exc:
        return _error_response(
            ErrorCode.DECK_NOT_FOUND,
            "Deck not found.",
            404,
            resource_type="deck",
            resource_id=getattr(exc, "deck_id", None),
            resource_name=getattr(exc, "resource_name", None),
        )

    return FlashcardResponse.model_validate(card)


@router.delete(
    "/cards/{card_id}",
    status_code=200,
    response_model=None,
    dependencies=[Depends(require_user_scope(PermissionScope.DECKS_WRITE))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Delete card",
)
async def delete_card(
    card_id: str,
    current_user: User = _current_user_dep,
    db: AsyncSession = _db_dep,
) -> Response:
    try:
        await flashcard_service.delete_card(db, current_user.id, card_id)
    except CardNotFoundError as exc:
        return _card_not_found(
            getattr(exc, "card_id", card_id), getattr(exc, "resource_name", None)
        )
    except DeckNotFoundError as exc:
        return _deck_not_found(getattr(exc, "deck_id", None), getattr(exc, "resource_name", None))

    return Response(status_code=200)
