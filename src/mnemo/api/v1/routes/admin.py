"""
Admin routes.
Uses unified provisioning function, supports both test and live API keys.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.api.dependencies import get_current_user_from_token, require_user_scope
from mnemo.core.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, ErrorCode, PermissionScope
from mnemo.core.exceptions import (
    DisplayNameConflictError,
    EmailConflictError,
    InvalidCountryCodeError,
    InvalidTimezoneError,
    MissingTimezoneError,
)
from mnemo.db.database import get_db
from mnemo.models.user import User
from mnemo.schemas.deck import DeckListItem, DeckListResponse
from mnemo.schemas.error import ErrorResponse
from mnemo.schemas.user import (
    ProvisionResponse,
    UserListItem,
    UserListResponse,
    UserProvisionRequest,
)
from mnemo.services import deck as deck_service
from mnemo.services import user as user_service

router = APIRouter(prefix="/admin", tags=["admin"])
db_dep = Depends(get_db)
current_user_dep = Depends(get_current_user_from_token)
_require_admin = Depends(require_user_scope(PermissionScope.ADMIN))


@router.post(
    "/provision",
    status_code=201,
    response_model=ProvisionResponse,
    dependencies=[_require_admin],
    responses={
        201: {
            "description": "User created; returns a one-time API key and its type (live or test)",
            "content": {
                "application/json": {
                    "example": {
                        "user_id": "usr_9c8b7a6d5e4f3a21",
                        "email": "new.user@example.com",
                        "api_key": "mnm_live_examplekey",
                        "key_type": "live",
                        "display_name": "New User",
                        "role": "user",
                        "email_verified": True,
                    }
                }
            },
        },
        403: {"model": ErrorResponse, "description": "Admin JWT required"},
        409: {"model": ErrorResponse, "description": "Email or display name already taken"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
    summary="Admin — provision a new user",
    description=(
        "Admin-only. Creates a new user account, optionally assigning role='admin'. "
        "Can create either test or live API keys via the create_live_key parameter. "
        "Returns a one-time plain API key — store it immediately."
    ),
)
async def admin_provision_user(
    body: UserProvisionRequest,
    current_user: User = current_user_dep,
    db: AsyncSession = db_dep,
) -> ProvisionResponse:
    """
    Admin provisions a new user (optionally admin role, optionally live key).

    UNIFIED with public registration - uses the same provision_user service function.
    """
    # Default to "user" role if not specified
    role = body.role or "user"

    # Admin can create live keys via the create_live_key parameter
    create_live_key = body.create_live_key

    try:
        user, plain_api_key, key_type = await user_service.provision_user(
            db=db,
            email=body.email,
            password=body.password,
            country=body.country,
            timezone=body.timezone,
            display_name=body.display_name,
            role=role,
            create_live_key=create_live_key,
            preferred_language=body.preferred_language,
            daily_goal_cards=body.daily_goal_cards,
        )
    except (
        EmailConflictError,
        DisplayNameConflictError,
        InvalidCountryCodeError,
        InvalidTimezoneError,
        MissingTimezoneError,
    ) as e:
        from mnemo.api.v1.routes.provision import _raise_provision_http_error

        _raise_provision_http_error(e)

    return ProvisionResponse(
        user_id=user.id,
        email=user.email,
        api_key=plain_api_key,
        key_type=key_type,
        display_name=user.display_name,
        role=user.role,
        email_verified=user.email_verified,
    )


@router.get(
    "/users",
    response_model=UserListResponse,
    dependencies=[_require_admin],
    responses={
        403: {"model": ErrorResponse, "description": "Admin JWT required"},
    },
    summary="Admin — list all users",
    description=(
        "Returns a paginated list of all users with deck counts. "
        "Searchable by email or display name."
    ),
)
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    search: str | None = Query(None, description="Partial match on display_name or email"),
    db: AsyncSession = db_dep,
) -> UserListResponse:
    """List all users (admin only)."""
    rows, total = await user_service.list_users(db, page=page, per_page=per_page, search=search)

    items = [
        UserListItem(
            user_id=user.id,
            email=user.email,
            display_name=user.display_name,
            country=user.country,
            role=user.role,
            email_verified=user.email_verified,
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
        "Returns the target user's deck list. Requires a valid admin JWT and either:\n"
        "1. The target user's global admin_access_granted flag is set, or\n"
        "2. The target user has granted resource-specific consent via POST "
        '/v1/user/grant-admin-access (resource="decks")\n\n'
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

    # Consent gate — must be checked AFTER admin JWT verification
    has_global_flag = bool(target_user.admin_access_granted)
    has_consent = await user_service.has_admin_consent(db=db, user_id=user_id, resource="decks")
    if not (has_global_flag or has_consent):
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
