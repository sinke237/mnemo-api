"""
User provisioning routes.
Unified public self-registration and admin user creation.
"""

import logging
from datetime import UTC, datetime
from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.api.dependencies import get_current_user_from_token
from mnemo.core.constants import ErrorCode
from mnemo.core.exceptions import (
    DisplayNameConflictError,
    EmailConflictError,
    InvalidCountryCodeError,
    InvalidTimezoneError,
    MissingTimezoneError,
)
from mnemo.db.database import get_db
from mnemo.models.user import User
from mnemo.schemas.error import ErrorResponse
from mnemo.schemas.user import (
    GrantAdminAccessRequest,
    GrantAdminAccessResponse,
    ProvisionResponse,
    UserProvisionRequest,
)
from mnemo.services import user as user_service

router = APIRouter(prefix="/user", tags=["user"])
db_dep = Depends(get_db)
current_user_dep = Depends(get_current_user_from_token)
logger = logging.getLogger(__name__)


def _raise_provision_http_error(exc: Exception) -> NoReturn:
    """Translate service exceptions into HTTPException with consistent payloads."""
    if isinstance(exc, EmailConflictError):
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": ErrorCode.EMAIL_CONFLICT.value,
                    "message": str(exc),
                    "status": 409,
                }
            },
        ) from None
    if isinstance(exc, DisplayNameConflictError):
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": ErrorCode.DISPLAY_NAME_CONFLICT.value,
                    "message": str(exc),
                    "status": 409,
                }
            },
        ) from None
    if isinstance(exc, InvalidCountryCodeError):
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": ErrorCode.INVALID_COUNTRY_CODE.value,
                    "message": str(exc),
                    "status": 422,
                }
            },
        ) from None
    if isinstance(exc, InvalidTimezoneError | MissingTimezoneError):
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": ErrorCode.INVALID_TIMEZONE.value,
                    "message": str(exc),
                    "status": 422,
                }
            },
        ) from None
    raise exc


@router.post(
    "/provision",
    status_code=201,
    response_model=ProvisionResponse,
    responses={
        201: {
            "description": "User created; returns a one-time API key and its type",
            "content": {
                "application/json": {
                    "example": {
                        "user_id": "usr_03291e0f40ef7357",
                        "email": "enow.sinke@example.com",
                        "api_key": "mnm_test_examplekey",
                        "key_type": "test",
                        "display_name": "Enow Sinke",
                        "role": "user",
                        "email_verified": False,
                    }
                }
            },
        },
        409: {"model": ErrorResponse, "description": "Email or display name already taken"},
        422: {
            "model": ErrorResponse,
            "description": "Invalid country, missing timezone, or validation error",
        },
    },
    summary="Self-register a new user account",
    description=(
        "Public endpoint — no authentication required.\n\n"
        "Creates a new regular-role user account with email + password and returns "
        "a one-time plain API key (test key by default). Store the API key immediately; "
        "it will not be shown again.\n\n"
        "After registration, a verification email will be sent (TODO). "
        "Email verification is required for certain features."
    ),
)
async def provision_user(
    body: UserProvisionRequest,
    db: AsyncSession = db_dep,
) -> ProvisionResponse:
    """
    Register a new user (public, no auth required).

    ALWAYS creates a test API key for public registrations.
    """
    try:
        user, plain_api_key, key_type = await user_service.provision_user(
            db=db,
            email=body.email,
            password=body.password,
            country=body.country,
            timezone=body.timezone,
            display_name=body.display_name,
            role="user",  # Public registration always creates regular users
            create_live_key=False,  # Public registration always creates test keys
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
        _raise_provision_http_error(e)

    # TODO: Send email verification email here

    return ProvisionResponse(
        user_id=user.id,
        email=user.email,
        api_key=plain_api_key,
        key_type=key_type,
        display_name=user.display_name,
        role=user.role,
        email_verified=user.email_verified,
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
        "allowing admin users (with a valid admin JWT) to view their deck list via "
        "GET /v1/admin/users/{userId}/decks. Admin access requires a valid admin JWT "
        "and either the target user's global `admin_access_granted` flag or a per-resource "
        'consent created via POST /v1/user/grant-admin-access (resource="decks").\n\n'
        "NOTE: This is separate from admin role authentication. Admin users "
        "authenticate via their role field, not this consent flag."
    ),
)
async def grant_admin_access(
    body: GrantAdminAccessRequest | None = None,
    current_user: User = current_user_dep,
    db: AsyncSession = db_dep,
) -> GrantAdminAccessResponse:
    """Allow admin users to view this user's deck list.

    If a body is supplied, create a per-resource consent record. If no body is
    supplied, preserve legacy behavior and set the user's global boolean flag.
    """
    # Explicitly declare nullable datetime for mypy type correctness
    granted_at: datetime | None = None

    if body is None or body.resource is None:
        # Legacy/global behavior
        current_user.admin_access_granted = True
        current_user.admin_access_granted_at = datetime.now(UTC)
        await db.flush()
        granted_at = current_user.admin_access_granted_at
        # Defensive: ensure granted_at is a serializable datetime or None
        try:
            if granted_at is not None and not isinstance(granted_at, datetime):
                # Coerce via isoformat if possible, otherwise discard
                granted_at = datetime.fromisoformat(str(granted_at))
        except (ValueError, TypeError):
            logger.exception("Failed to parse granted_at value: %r", granted_at)
            granted_at = None
    else:
        # Create per-resource consent and use the persisted timestamp if available
        consent = await user_service.create_admin_consent(
            db=db,
            user_id=current_user.id,
            resource=body.resource,
            resource_id=body.resource_id,
            expires_at=body.expires_at,
        )
        # Backwards-compatible: if the service returns None, fall back to local time
        if consent is None:
            granted_at = datetime.now(UTC)
        else:
            granted_at = getattr(consent, "granted_at", datetime.now(UTC))
        # Defensive: ensure granted_at is a serializable datetime or None
        try:
            if granted_at is not None and not isinstance(granted_at, datetime):
                granted_at = datetime.fromisoformat(str(granted_at))
        except (ValueError, TypeError):
            logger.exception("Failed to parse granted_at value from consent: %r", granted_at)
            granted_at = None

    # Return a JSONResponse with serializable types to avoid accidental
    # non-serializable values (e.g., exception objects) making it into the body.
    return GrantAdminAccessResponse(
        admin_access_granted=True,
        granted_at=granted_at,
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
    body: GrantAdminAccessRequest | None = None,
    current_user: User = current_user_dep,
    db: AsyncSession = db_dep,
) -> GrantAdminAccessResponse:
    """Revoke admin users' permission to view this user's deck list.

    If a body is supplied, revoke matching per-resource consents. If no body is
    supplied, preserve legacy behavior and clear the user's global flag.
    """
    if body is None or body.resource is None:
        # Revoke any per-resource consents as well as the global flag so that
        # the effective access (has_admin_consent OR admin_access_granted)
        # is fully revoked.
        await user_service.revoke_admin_consent(db=db, user_id=current_user.id)
        current_user.admin_access_granted = False
        current_user.admin_access_granted_at = None
        await db.flush()
        return GrantAdminAccessResponse(admin_access_granted=False, granted_at=None)

    # Revoke per-resource consents matching the body and also clear the
    # global admin_access_granted flag to ensure access is fully revoked.
    await user_service.revoke_admin_consent(
        db=db, user_id=current_user.id, resource=body.resource, resource_id=body.resource_id
    )
    current_user.admin_access_granted = False
    current_user.admin_access_granted_at = None
    await db.flush()
    return GrantAdminAccessResponse(admin_access_granted=False, granted_at=None)
