"""
Admin routes.
Provides user management and consent-gated deck access for admin users.

All endpoints require a valid JWT with role = "admin" (scope = "admin").
Non-admin JWTs receive 403, not 401.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.api.dependencies import get_current_user_from_token, require_user_scope
from mnemo.core.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, ErrorCode, PermissionScope
from mnemo.core.exceptions import (
    DisplayNameConflictError,
    InvalidCountryCodeError,
    InvalidTimezoneError,
    MissingTimezoneError,
)
from mnemo.db.database import get_db
from mnemo.models.user import User
from mnemo.schemas.deck import DeckListItem, DeckListResponse
from mnemo.schemas.error import ErrorResponse
from mnemo.schemas.user import (
    AdminProvisionRequest,
    ProvisionResponse,
    UserListItem,
    UserListResponse,
)
from mnemo.services import deck as deck_service
from mnemo.services import user as user_service

router = APIRouter(prefix="/admin", tags=["admin"])
# module-level Depends singletons to satisfy ruff B008
db_dep = Depends(get_db)
current_user_dep = Depends(get_current_user_from_token)
_require_admin = Depends(require_user_scope(PermissionScope.ADMIN))


@router.post(
    "/provision",
    status_code=201,
    response_model=ProvisionResponse,
    dependencies=[_require_admin],
    responses={
        403: {"model": ErrorResponse, "description": "Admin JWT required"},
        409: {"model": ErrorResponse, "description": "Display name already taken"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
    summary="Admin — provision a new user",
    description=(
        "Admin-only. Creates a new user account, optionally assigning role='admin'. "
        "Returns a one-time plain API key — store it immediately."
    ),
)
async def admin_provision_user(
    body: AdminProvisionRequest,
    current_user: User = current_user_dep,
    db: AsyncSession = db_dep,
) -> ProvisionResponse:
    """Admin provisions a new user (optionally admin role)."""
    role = body.role or "user"

    try:
        user, plain_api_key = await user_service.provision_user(
            db=db,
            display_name=body.display_name,
            country=body.country,
            timezone=body.timezone,
            password=body.password,
            role=role,
        )
    except DisplayNameConflictError:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": ErrorCode.DISPLAY_NAME_CONFLICT.value,
                    "message": "Display name is already taken",
                    "status": 409,
                }
            },
        ) from None
    except InvalidCountryCodeError as e:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": ErrorCode.INVALID_COUNTRY_CODE.value,
                    "message": str(e),
                    "status": 422,
                }
            },
        ) from None
    except (InvalidTimezoneError, MissingTimezoneError) as e:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": ErrorCode.INVALID_TIMEZONE.value,
                    "message": str(e),
                    "status": 422,
                }
            },
        ) from None

    return ProvisionResponse(
        user_id=user.id,
        api_key=plain_api_key,
        display_name=user.display_name,
        role=user.role,
    )


@router.get(
    "/users",
    response_model=UserListResponse,
    dependencies=[_require_admin],
    responses={
        403: {"model": ErrorResponse, "description": "Admin JWT required"},
    },
    summary="Admin — list all users",
    description="Returns a paginated list of all users with deck counts.",
)
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    search: str | None = Query(None, description="Partial match on display_name"),
    db: AsyncSession = db_dep,
) -> UserListResponse:
    """List all users (admin only)."""
    rows, total = await user_service.list_users(db, page=page, per_page=per_page, search=search)

    items = [
        UserListItem(
            user_id=user.id,
            display_name=user.display_name,
            country=user.country,
            role=user.role,
            created_at=user.created_at,
            deck_count=deck_count,
            has_granted_admin_access=user.admin_access_granted,
        )
        for user, deck_count in rows
    ]

    return UserListResponse(users=items, total=total, page=page, per_page=per_page)


@router.delete(
    "/users/{user_id}",
    status_code=204,
    dependencies=[_require_admin],
    responses={
        400: {"model": ErrorResponse, "description": "Cannot delete your own account"},
        403: {"model": ErrorResponse, "description": "Admin JWT required"},
        404: {"model": ErrorResponse, "description": "User not found"},
    },
    summary="Admin — delete a user",
    description=(
        "Permanently removes a user and all associated data (decks, cards, sessions, "
        "API keys). Uses a DB-level transaction. Returns 400 if admin tries to delete "
        "their own account."
    ),
)
async def delete_user(
    user_id: str,
    current_user: User = current_user_dep,
    db: AsyncSession = db_dep,
) -> None:
    """Delete a user and all their data (admin only)."""
    if current_user.id == user_id:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": ErrorCode.VALIDATION_ERROR.value,
                    "message": "Admins cannot delete their own account",
                    "status": 400,
                }
            },
        )

    deleted = await user_service.delete_user(db, user_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": ErrorCode.USER_NOT_FOUND.value,
                    "message": "User not found",
                    "status": 404,
                }
            },
        )


@router.get(
    "/users/{user_id}/decks",
    response_model=DeckListResponse,
    dependencies=[_require_admin],
    responses={
        403: {"model": ErrorResponse, "description": "Admin JWT required or access not granted"},
        404: {"model": ErrorResponse, "description": "User not found"},
    },
    summary="Admin — view a user's decks (consent-gated)",
    description=(
        "Returns the target user's deck list.  Requires **both**:\n"
        "1. A valid admin JWT (403 otherwise)\n"
        "2. The target user has called POST /v1/user/grant-admin-access (403 otherwise)\n\n"
        "Response shape is identical to GET /v1/decks."
    ),
)
async def get_user_decks(
    user_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    tag: str | None = None,
    db: AsyncSession = db_dep,
) -> DeckListResponse:
    """
    Return a user's decks — both admin JWT and user consent are required.

    The admin_access_granted check runs AFTER the JWT admin-scope check so that both
    requirements are enforced and neither leaks information about the other.
    """
    # Fetch target user
    target_user = await user_service.get_user_by_id(db, user_id)
    if target_user is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": ErrorCode.USER_NOT_FOUND.value,
                    "message": "User not found",
                    "status": 404,
                }
            },
        )

    # Consent gate — must be checked AFTER admin JWT verification (enforced by _require_admin)
    if not target_user.admin_access_granted:
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": ErrorCode.ADMIN_ACCESS_NOT_GRANTED.value,
                    "message": "User has not granted admin access",
                    "status": 403,
                }
            },
        )

    decks, pagination = await deck_service.list_decks(
        db,
        user_id=user_id,
        page=page,
        per_page=per_page,
        tag=tag,
    )
    return DeckListResponse(
        data=[DeckListItem.model_validate(deck) for deck in decks],
        pagination=pagination,
    )
