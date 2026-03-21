from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.api.dependencies import get_current_user_from_token, get_db, require_user_scope
from mnemo.core.constants import ErrorCode, HTTPStatusCode, PermissionScope
from mnemo.models.deck import Deck
from mnemo.models.user import User
from mnemo.schemas.error import ErrorResponse
from mnemo.schemas.progress import DeckProgressResponse, ProgressResponse, StreakResponse
from mnemo.services import progress as progress_service
from mnemo.services.user import get_user_by_id

router = APIRouter(prefix="/users", tags=["progress"])
db_dep = Depends(get_db)
current_user_dep = Depends(get_current_user_from_token)


def _authorize(user: User, target_user_id: str) -> None:
    if user.id != target_user_id:
        scopes = getattr(user, "token_scopes", []) or []
        if PermissionScope.ADMIN.value not in scopes:
            raise HTTPException(
                status_code=HTTPStatusCode.FORBIDDEN,
                detail={
                    "error": {
                        "code": ErrorCode.INSUFFICIENT_SCOPE.value,
                        "message": "Cannot access another user's progress",
                        "status": HTTPStatusCode.FORBIDDEN,
                    }
                },
            )


async def _get_target_user(db: AsyncSession, user_id: str) -> User:
    """Look up the target user by ID; raise 404 if not found."""
    user = await get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=HTTPStatusCode.NOT_FOUND,
            detail={
                "error": {
                    "code": ErrorCode.USER_NOT_FOUND.value,
                    "message": f"User not found: {user_id}",
                    "status": HTTPStatusCode.NOT_FOUND,
                }
            },
        )
    return user


@router.get(
    "/{user_id}/progress",
    response_model=ProgressResponse,
    status_code=HTTPStatusCode.OK,
    responses={
        HTTPStatusCode.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatusCode.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatusCode.NOT_FOUND: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_user_scope(PermissionScope.PROGRESS_READ))],
)
async def get_progress(
    user_id: str, db: AsyncSession = db_dep, current_user: User = current_user_dep
) -> ProgressResponse:
    _authorize(current_user, user_id)
    target_user = await _get_target_user(db, user_id)
    data = await progress_service.get_user_progress(db, target_user)
    return ProgressResponse.model_validate(data)


@router.get(
    "/{user_id}/progress/{deck_id}",
    response_model=DeckProgressResponse,
    status_code=HTTPStatusCode.OK,
    responses={
        HTTPStatusCode.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatusCode.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatusCode.NOT_FOUND: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_user_scope(PermissionScope.PROGRESS_READ))],
)
async def get_deck_progress(
    user_id: str, deck_id: str, db: AsyncSession = db_dep, current_user: User = current_user_dep
) -> DeckProgressResponse:
    _authorize(current_user, user_id)
    target_user = await _get_target_user(db, user_id)
    # Ensure the deck exists and belongs to the target user
    result = await db.execute(
        select(Deck).where(Deck.id == deck_id, Deck.user_id == target_user.id)
    )
    deck = result.scalar_one_or_none()
    if not deck:
        raise HTTPException(
            status_code=HTTPStatusCode.NOT_FOUND,
            detail={
                "error": {
                    "code": ErrorCode.DECK_NOT_FOUND.value,
                    "message": f"Deck not found: {deck_id}",
                    "status": HTTPStatusCode.NOT_FOUND,
                }
            },
        )

    data = await progress_service.get_deck_progress(db, target_user, deck_id)
    return DeckProgressResponse.model_validate(data)


@router.get(
    "/{user_id}/streak",
    response_model=StreakResponse,
    status_code=HTTPStatusCode.OK,
    responses={
        HTTPStatusCode.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatusCode.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatusCode.NOT_FOUND: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_user_scope(PermissionScope.PROGRESS_READ))],
)
async def get_streak(
    user_id: str, db: AsyncSession = db_dep, current_user: User = current_user_dep
) -> StreakResponse:
    _authorize(current_user, user_id)
    target_user = await _get_target_user(db, user_id)
    data = await progress_service.get_user_streak(db, target_user)
    return StreakResponse.model_validate(
        {
            "streak": data["streak"],
            "last_studied_at": data.get("last_studied_at"),
            "last_studied_at_local": data.get("last_studied_at_local"),
        }
    )
