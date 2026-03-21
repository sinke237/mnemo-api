"""
Study plan routes.
POST /users/{id}/plan  — generate a new study plan       (sessions:run scope)
GET  /users/{id}/plan  — retrieve the active study plan  (progress:read scope)
Per spec FR-07.2 and section 11.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.api.dependencies import get_current_user_from_token, get_db, require_user_scope
from mnemo.core.constants import ErrorCode, HTTPStatusCode, PermissionScope
from mnemo.core.exceptions import DeckNotFoundError, PlanNotFoundError
from mnemo.models.user import User
from mnemo.schemas.error import ErrorResponse
from mnemo.schemas.plan import PlanCreate, PlanResponse
from mnemo.services import plan as plan_service
from mnemo.services.user import get_user_by_id

router = APIRouter(prefix="/users", tags=["plan"])
db_dep = Depends(get_db)
current_user_dep = Depends(get_current_user_from_token)


def _authorize(current_user: User, target_user_id: str) -> None:
    if current_user.id != target_user_id:
        scopes = getattr(current_user, "token_scopes", []) or []
        if PermissionScope.ADMIN.value not in scopes:
            raise HTTPException(
                status_code=HTTPStatusCode.FORBIDDEN,
                detail={
                    "error": {
                        "code": ErrorCode.INSUFFICIENT_SCOPE.value,
                        "message": "Cannot access another user's plan",
                        "status": HTTPStatusCode.FORBIDDEN,
                    }
                },
            )


async def _get_target_user(db: AsyncSession, user_id: str) -> User:
    user = await get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=HTTPStatusCode.NOT_FOUND,
            detail={
                "error": {
                    "code": ErrorCode.USER_NOT_FOUND.value,
                    "message": "User not found.",
                    "status": HTTPStatusCode.NOT_FOUND,
                    "resource": {"type": "user", "id": user_id},
                }
            },
        )
    return user


@router.post(
    "/{user_id}/plan",
    response_model=PlanResponse,
    status_code=HTTPStatusCode.CREATED,
    responses={
        HTTPStatusCode.BAD_REQUEST: {"model": ErrorResponse},
        HTTPStatusCode.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatusCode.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatusCode.NOT_FOUND: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_user_scope(PermissionScope.SESSIONS_RUN))],
    summary="Generate a study plan",
    description=(
        "Generates a structured daily study schedule for the user. "
        "Schedule dates reflect the user's local calendar (FR-07.2)."
    ),
)
async def create_plan(
    user_id: str,
    body: PlanCreate,
    db: AsyncSession = db_dep,
    current_user: User = current_user_dep,
) -> PlanResponse:
    _authorize(current_user, user_id)
    target_user = await _get_target_user(db, user_id)

    try:
        plan = await plan_service.create_plan(
            db=db,
            user=target_user,
            deck_id=body.deck_id,
            goal=body.goal,
            days=body.days,
            daily_minutes=body.daily_minutes,
        )
    except DeckNotFoundError as err:
        raise HTTPException(
            status_code=HTTPStatusCode.NOT_FOUND,
            detail={
                "error": {
                    "code": ErrorCode.DECK_NOT_FOUND.value,
                    "message": "Deck not found.",
                    "status": HTTPStatusCode.NOT_FOUND,
                    "resource": {"type": "deck", "id": body.deck_id},
                }
            },
        ) from err

    return PlanResponse(
        plan_id=plan.id,
        deck_id=plan.deck_id,
        goal=plan.goal,
        days=plan.days,
        daily_target=plan.daily_target,
        daily_minutes=plan.daily_minutes,
        schedule=plan.schedule,
        created_at=plan.created_at,
    )


@router.get(
    "/{user_id}/plan",
    response_model=PlanResponse,
    status_code=HTTPStatusCode.OK,
    responses={
        HTTPStatusCode.UNAUTHORIZED: {"model": ErrorResponse},
        HTTPStatusCode.FORBIDDEN: {"model": ErrorResponse},
        HTTPStatusCode.NOT_FOUND: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_user_scope(PermissionScope.PROGRESS_READ))],
    summary="Get active study plan",
    description="Returns the most recently generated study plan for the user.",
)
async def get_plan(
    user_id: str,
    db: AsyncSession = db_dep,
    current_user: User = current_user_dep,
) -> PlanResponse:
    _authorize(current_user, user_id)
    await _get_target_user(db, user_id)

    try:
        plan = await plan_service.get_active_plan(db, user_id)
    except PlanNotFoundError as err:
        raise HTTPException(
            status_code=HTTPStatusCode.NOT_FOUND,
            detail={
                "error": {
                    "code": ErrorCode.PLAN_NOT_FOUND.value,
                    "message": "No active study plan for user.",
                    "status": HTTPStatusCode.NOT_FOUND,
                    "resource": {"type": "user", "id": user_id},
                }
            },
        ) from err

    return PlanResponse(
        plan_id=plan.id,
        deck_id=plan.deck_id,
        goal=plan.goal,
        days=plan.days,
        daily_target=plan.daily_target,
        daily_minutes=plan.daily_minutes,
        schedule=plan.schedule,
        created_at=plan.created_at,
    )
