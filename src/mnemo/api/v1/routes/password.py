"""
Password management routes.
Handles password change and reset functionality.
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.api.dependencies import get_current_user_from_token
from mnemo.core.config import get_settings
from mnemo.core.constants import ErrorCode
from mnemo.db.database import get_db
from mnemo.db.redis import get_redis
from mnemo.models.user import User
from mnemo.schemas.error import ErrorResponse
from mnemo.schemas.user import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    RequestPasswordResetRequest,
    RequestPasswordResetResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
)
from mnemo.services import email as email_service
from mnemo.services import password_reset as password_reset_service
from mnemo.services import user as user_service
from mnemo.utils.password import get_password_hash, verify_password

router = APIRouter(prefix="/user", tags=["user"])
db_dep = Depends(get_db)
current_user_dep = Depends(get_current_user_from_token)


@router.post(
    "/change-password",
    response_model=ChangePasswordResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid current password or no token"},
    },
    summary="Change password",
    description="Change your password. Requires valid JWT token and current password verification.",
)
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = current_user_dep,
    db: AsyncSession = db_dep,
) -> ChangePasswordResponse:
    """Change the authenticated user's password."""

    # Verify user has a password set
    if current_user.password_hash is None:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": ErrorCode.VALIDATION_ERROR.value,
                    "message": "Account has no password set. Use password reset to set one.",
                    "status": 400,
                }
            },
        )

    # Verify current password
    if not verify_password(request.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": ErrorCode.INVALID_CREDENTIALS.value,
                    "message": "Current password is incorrect",
                    "status": 401,
                }
            },
        )

    # Hash and save new password
    current_user.password_hash = get_password_hash(request.new_password)
    await db.flush()

    return ChangePasswordResponse()


@router.post(
    "/request-password-reset",
    response_model=RequestPasswordResetResponse,
    summary="Request password reset email",
    description=(
        "Public endpoint. Send a password reset email to the provided address. "
        "Always returns 200 regardless of whether the email exists (prevents enumeration). "
        "If an account exists, an email with a reset link will be sent."
    ),
)
async def request_password_reset(
    request: RequestPasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = db_dep,
) -> RequestPasswordResetResponse:
    """
    Request a password reset email.

    Security: Always returns success to prevent email enumeration.
    """
    # Always return success to avoid account enumeration
    # If an account exists, create a reset token and enqueue an email
    try:
        user = await user_service.get_user_by_email(db, request.email)
    except Exception:
        user = None

    if user is not None:
        # Rate limit password reset requests per email to mitigate abuse.
        settings = get_settings()
        redis = get_redis()
        try:
            # Use non-PII identifier for rate-limiting key (avoid raw email)
            key = f"prr:{user.id}"
            # Atomic INCR + EXPIRE via EVAL (same pattern as rate limit middleware)
            lua = (
                "local c=redis.call('INCR', KEYS[1]); "
                "if c==1 then redis.call('EXPIRE', KEYS[1], tonumber(ARGV[1])) end; return c"
            )
            try:
                count = await redis.eval(lua, 1, key, 3600)
            except Exception:
                # Fallback for clients that don't support eval similarly
                count = await redis.incr(key)
                if count == 1:
                    await redis.expire(key, 3600)

            if count > settings.password_reset_rate_limit_per_hour:
                # Silently succeed to avoid enumeration, but do not send another email.
                return RequestPasswordResetResponse()
        except Exception:
            # If Redis is unavailable, fall back to best-effort behavior but
            # record a warning so operators can investigate underlying issues.
            logger = logging.getLogger(__name__)
            logger.warning(
                "Redis unavailable for password reset rate limiting; continuing without rate-limit",
                exc_info=True,
            )

        # Create token and enqueue email in the background. Token is returned
        # plaintext once by create_token and stored hashed in DB. Wrap in
        # try/except so side-effect failures don't enable enumeration.
        try:
            token = await password_reset_service.create_token(db, user.id)
            # Attach optional request id if present in state (for tracing)
            # The password reset model has an optional `request_id` column; callers
            # may populate this if desired.
            settings = get_settings()
            frontend = getattr(settings, "frontend_base_url", settings.api_base_url)
            reset_url = f"{frontend}/reset-password#token={token}"
            # Enqueue sending the email via BackgroundTasks (placeholder service)
            background_tasks.add_task(
                email_service.send_password_reset_email, user.email, reset_url, user_id=user.id
            )
        except Exception:
            logger = logging.getLogger(__name__)
            logger.exception(
                "Failed to create or send password reset token",
                extra={"user_id": getattr(user, "id", None), "email": getattr(user, "email", None)},
            )
            # Roll back DB transaction on failure of side-effects so state isn't partially applied
            try:
                await db.rollback()
            except Exception:
                # Log rollback failures for operator visibility but do not
                # re-raise so the endpoint stays idempotent from the caller's
                # perspective.
                logging.exception("Failed to rollback DB after password reset side-effect failure")
            return RequestPasswordResetResponse()

    return RequestPasswordResetResponse()


@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid or expired token"},
        501: {"model": ErrorResponse, "description": "Not Implemented"},
    },
    summary="Reset password with token",
    description=(
        "Public endpoint. Reset password using a token received via email. "
        "The token is valid for 1 hour after the reset request."
    ),
)
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncSession = db_dep,
) -> ResetPasswordResponse:
    """
    Reset password using a token from email.

    TODO: Implement token validation and password reset.
    """
    # 1. Atomically validate token and mark it used to prevent reuse/races
    token_row = await password_reset_service.consume_token_by_plain(db, request.token)
    if token_row is None:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": ErrorCode.INVALID_TOKEN.value,
                    "message": "Invalid or expired token",
                    "status": 400,
                }
            },
        )

    # 2. Resolve user (token stores user_id)
    # Avoid accessing relationship attributes directly (which may trigger
    # lazy-load IO in async context). Check the instance dict first to
    # determine if the relationship is already loaded; otherwise fetch.
    user = token_row.__dict__.get("user")
    if user is None:
        user = await user_service.get_user_by_id(db, token_row.user_id)

    if user is None:
        # Token references a missing user — treat as invalid
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": ErrorCode.INVALID_TOKEN.value,
                    "message": "Invalid or expired token",
                    "status": 400,
                }
            },
        )

    # 3. Update the user's password (token already marked used)
    user.password_hash = get_password_hash(request.new_password)
    await db.flush()

    return ResetPasswordResponse()
