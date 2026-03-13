"""
User profile routes.
Handles user CRUD operations per spec section 11: User Profiles.
"""

import inspect

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.api.dependencies import (
    get_current_user_from_token,
    require_scope,
)
from mnemo.core.constants import ErrorCode, PermissionScope
from mnemo.db.database import get_db
from mnemo.models.user import User
from mnemo.schemas.error import ErrorResponse
from mnemo.schemas.user import UserCreate, UserResponse, UserUpdate
from mnemo.services import user as user_service

router = APIRouter(prefix="/users", tags=["users"])
# module-level Depends singletons to satisfy ruff B008
db_dep = Depends(get_db)
current_user_dep = Depends(get_current_user_from_token)


def _map_value_error_to_error_code(e: ValueError) -> ErrorCode:
    msg = str(e).lower()
    if "timezone" in msg or "missing timezone" in msg or "multiple timezones" in msg:
        return ErrorCode.INVALID_TIMEZONE
    elif "country" in msg or "unsupported country" in msg:
        return ErrorCode.INVALID_COUNTRY_CODE
    return ErrorCode.VALIDATION_ERROR


@router.post(
    "",
    status_code=201,
    dependencies=[Depends(require_scope(PermissionScope.ADMIN))],
    responses={
        400: {"model": ErrorResponse, "description": "Invalid country code or timezone"},
        401: {"model": ErrorResponse, "description": "Invalid API key"},
        403: {"model": ErrorResponse, "description": "Insufficient scope (requires admin)"},
    },
    summary="Create a new user",
    description=(
        "Create a new user account. Requires admin scope. "
        "Country is REQUIRED and determines the user's timezone. "
        "For multi-timezone countries (US, CA, BR, AU, RU, MX), "
        "the timezone field must be explicitly provided."
    ),
)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = db_dep,
) -> UserResponse:
    """
    Create a new user account.

    Per spec FR-07.1:
    - country is REQUIRED (ISO 3166-1 alpha-2)
    - timezone is derived from country or must be provided for multi-timezone countries
    - Location is never auto-detected
    """
    try:
        user = await user_service.create_user(db, user_data)
        return UserResponse.model_validate(user)

    except ValueError as e:
        error_code = _map_value_error_to_error_code(e)

        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": error_code.value,
                    "message": str(e),
                    "status": 400,
                }
            },
        ) from e


@router.get(
    "/{user_id}",
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or expired token"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "User not found"},
    },
    summary="Get user profile",
    description=(
        "Retrieve a user's profile. Requires valid JWT token for the user. "
        "Returns timezone as derived from country selection."
    ),
)
async def get_user(
    user_id: str,
    current_user: User = current_user_dep,
    db: AsyncSession = db_dep,
) -> UserResponse:
    """
    Get a user profile by ID.

    Security:
    - Users can only access their own profile
    - Admin scope can access any user
    """
    # Verify user is accessing their own profile. Admin-scoped tokens may
    # access any user's profile. The `get_current_user_from_token` dependency
    # attaches `token_scopes` to the returned User instance so we read that
    # attribute instead of re-decoding the raw token here.
    if current_user.id != user_id:
        scopes = getattr(current_user, "token_scopes", []) or []
        if PermissionScope.ADMIN.value not in scopes:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": {
                        "code": ErrorCode.INSUFFICIENT_SCOPE.value,
                        "message": "You can only access your own profile",
                        "status": 403,
                    }
                },
            )

    # Support service implementations or test fakes that may be sync or async.
    maybe = user_service.get_user_by_id(db, user_id)
    if inspect.isawaitable(maybe):
        user = await maybe
    else:
        user = maybe

    if user is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": ErrorCode.USER_NOT_FOUND.value,
                    "message": f"User not found: {user_id}",
                    "status": 404,
                }
            },
        )

    return UserResponse.model_validate(user)


@router.patch(
    "/{user_id}",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid timezone"},
        401: {"model": ErrorResponse, "description": "Invalid or expired token"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "User not found"},
    },
    summary="Update user profile",
    description=(
        "Update user profile fields. Country cannot be changed after creation. "
        "Timezone can only be updated for multi-timezone countries."
    ),
)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    current_user: User = current_user_dep,
    db: AsyncSession = db_dep,
) -> UserResponse:
    """
    Update user profile.

    Security:
    - Users can only update their own profile
    """
    # Verify user is updating their own profile
    if current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": ErrorCode.INSUFFICIENT_SCOPE.value,
                    "message": "You can only update your own profile",
                    "status": 403,
                }
            },
        )

    try:
        user = await user_service.update_user(db, user_id, user_data)

        if user is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": {
                        "code": ErrorCode.USER_NOT_FOUND.value,
                        "message": f"User not found: {user_id}",
                        "status": 404,
                    }
                },
            )

        return UserResponse.model_validate(user)

    except ValueError as e:
        error_code = _map_value_error_to_error_code(e)

        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": error_code.value,
                    "message": str(e),
                    "status": 400,
                }
            },
        ) from e
