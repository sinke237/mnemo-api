"""
User profile routes.
Handles user CRUD operations per spec section 11: User Profiles.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.api.dependencies import (
    get_current_user_from_token,
    require_scope,
)
from mnemo.core.constants import ErrorCode, PermissionScope
from mnemo.core.exceptions import (
    DisplayNameConflictError,
    EmailConflictError,
    InvalidCountryCodeError,
    InvalidTimezoneError,
    MissingTimezoneError,
    TimezoneNotAllowedError,
)
from mnemo.db.database import get_db
from mnemo.models.user import User
from mnemo.schemas.error import ErrorResponse
from mnemo.schemas.user import (
    ProvisionResponse,
    UserProvisionRequest,
    UserResponse,
    UserUpdate,
)
from mnemo.services import user as user_service

router = APIRouter(prefix="/users", tags=["users"])
# module-level Depends singletons to satisfy ruff B008
db_dep = Depends(get_db)
current_user_dep = Depends(get_current_user_from_token)


def _user_not_found(user_id: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "error": {
                "code": ErrorCode.USER_NOT_FOUND.value,
                "message": "User not found.",
                "status": 404,
                "resource": {"type": "user", "id": user_id},
            }
        },
    )


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
    user_data: UserProvisionRequest,
    db: AsyncSession = db_dep,
) -> UserResponse | ProvisionResponse:
    """
    Create a new user account.

    Per spec FR-07.1:
    - country is REQUIRED (ISO 3166-1 alpha-2)
    - timezone is derived from country or must be provided for multi-timezone countries
    - Location is never auto-detected
    """
    try:
        user, _plain_api_key, _key_type = await user_service.provision_user(
            db=db,
            email=user_data.email,
            password=user_data.password,
            country=user_data.country,
            timezone=user_data.timezone,
            display_name=user_data.display_name,
            role=user_data.role or "user",
            create_live_key=user_data.create_live_key,
        )

        # `user_service.provision_user` returns a plain API key as the
        # second tuple element when `create_live_key` is True. If the caller
        # requested creation of a live key, return the `ProvisionResponse`
        # which includes the one-time plaintext API key. Do NOT log or persist
        # the plaintext key anywhere else.
        if user_data.create_live_key:
            return ProvisionResponse.model_validate(
                {
                    "user_id": user.id,
                    "email": user.email,
                    "api_key": _plain_api_key,
                    "key_type": _key_type,
                    "display_name": user.display_name,
                    "role": user.role,
                    "email_verified": user.email_verified,
                }
            )

        return UserResponse.model_validate(user)

    except InvalidCountryCodeError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": ErrorCode.INVALID_COUNTRY_CODE.value,
                    "message": str(e),
                    "status": 400,
                }
            },
        ) from e

    except (InvalidTimezoneError, MissingTimezoneError) as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": ErrorCode.INVALID_TIMEZONE.value,
                    "message": str(e),
                    "status": 400,
                }
            },
        ) from e
    except EmailConflictError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": ErrorCode.EMAIL_CONFLICT.value,
                    "message": str(e),
                    "status": 409,
                }
            },
        ) from e
    except DisplayNameConflictError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": ErrorCode.DISPLAY_NAME_CONFLICT.value,
                    "message": str(e),
                    "status": 409,
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
    # Verify user is accessing their own profile or has admin scope
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

    # Fetch user (no more inspect.isawaitable - services are always async)
    user = await user_service.get_user_by_id(db, user_id)

    if user is None:
        raise _user_not_found(user_id)

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
            raise _user_not_found(user_id)

        return UserResponse.model_validate(user)

    except (InvalidTimezoneError, TimezoneNotAllowedError) as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": ErrorCode.INVALID_TIMEZONE.value,
                    "message": str(e),
                    "status": 400,
                }
            },
        ) from e
