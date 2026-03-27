"""
User self-service routes.
Handles public registration and admin-access consent toggling.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.api.dependencies import get_current_user_from_token
from mnemo.core.constants import ErrorCode
from mnemo.core.exceptions import (
    DisplayNameConflictError,
    InvalidCountryCodeError,
    InvalidTimezoneError,
    MissingTimezoneError,
)
from mnemo.db.database import get_db
from mnemo.models.user import User
from mnemo.schemas.error import ErrorResponse
from mnemo.schemas.user import GrantAdminAccessResponse, ProvisionResponse, UserProvisionRequest
from mnemo.services import user as user_service

router = APIRouter(prefix="/user", tags=["user"])
# module-level Depends singletons to satisfy ruff B008
db_dep = Depends(get_db)
current_user_dep = Depends(get_current_user_from_token)


@router.post(
    "/provision",
    status_code=201,
    response_model=ProvisionResponse,
    responses={
        409: {"model": ErrorResponse, "description": "Display name already taken"},
        422: {
            "model": ErrorResponse,
            "description": "Invalid country, missing timezone, or validation error",
        },
    },
    summary="Self-register a new user account",
    description=(
        "Public endpoint — no authentication required.\n\n"
        "Creates a new regular-role user account and returns a one-time plain API key. "
        "Store the API key immediately; it will not be shown again.\n\n"
        "If `password` is omitted the account is passwordless; authentication then "
        "requires POST /v1/auth/token with an API key.\n\n"
        # TODO: rate-limit this endpoint using the existing RateLimitMiddleware
        # (currently matched to the 'auth' category by _resolve_category_and_limit).
    ),
)
async def provision_user(
    body: UserProvisionRequest,
    db: AsyncSession = db_dep,
) -> ProvisionResponse:
    """Register a new user (public, no auth required)."""
    try:
        user, plain_api_key = await user_service.provision_user(
            db=db,
            display_name=body.display_name,
            country=body.country,
            timezone=body.timezone,
            password=body.password,
            role="user",
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


@router.post(
    "/grant-admin-access",
    response_model=GrantAdminAccessResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or expired token"},
    },
    summary="Grant admins access to your decks",
    description=(
        "Set `admin_access_granted = true` on the authenticated user's account, "
        "allowing any admin to view their deck list via "
        "GET /v1/admin/users/{userId}/decks."
    ),
)
async def grant_admin_access(
    current_user: User = current_user_dep,
    db: AsyncSession = db_dep,
) -> GrantAdminAccessResponse:
    """Allow admin users to view this user's deck list."""
    current_user.admin_access_granted = True
    current_user.admin_access_granted_at = datetime.now(UTC)
    await db.flush()

    return GrantAdminAccessResponse(
        admin_access_granted=True,
        granted_at=current_user.admin_access_granted_at,
    )


@router.delete(
    "/grant-admin-access",
    response_model=GrantAdminAccessResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or expired token"},
    },
    summary="Revoke admin access to your decks",
    description="Set `admin_access_granted = false`, revoking any admin's ability to view decks.",
)
async def revoke_admin_access(
    current_user: User = current_user_dep,
    db: AsyncSession = db_dep,
) -> GrantAdminAccessResponse:
    """Revoke admin users' permission to view this user's deck list."""
    current_user.admin_access_granted = False
    current_user.admin_access_granted_at = None
    await db.flush()

    return GrantAdminAccessResponse(
        admin_access_granted=False,
        granted_at=None,
    )
