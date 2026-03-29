"""
Password management routes.
Handles password change and reset functionality.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.api.dependencies import get_current_user_from_token
from mnemo.core.constants import ErrorCode
from mnemo.db.database import get_db
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
) -> RequestPasswordResetResponse:
    """
    Request a password reset email.

    Security: Always returns success to prevent email enumeration.
    """
    # Implementation not ready: mark as not implemented to avoid silently
    # claiming emails are sent while no token/email flow exists.
    raise HTTPException(
        status_code=501,
        detail={
            "error": {
                "code": "NOT_IMPLEMENTED",
                "message": (
                    "Password reset request flow not yet implemented. "
                    "TODO: generate token, persist it, and send reset email."
                ),
                "status": 501,
            }
        },
    )


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
    # TODO: Implement password reset
    # 1. Validate token (check expiry, format)
    # 2. Look up user associated with token
    # 3. If valid:
    #    a. Hash new password
    #    b. Update user.password_hash
    #    c. Invalidate/delete the reset token
    #    d. Return success
    # 4. If invalid/expired:
    #    a. Return 400 with appropriate error

    raise HTTPException(
        status_code=501,
        detail={
            "error": {
                "code": "NOT_IMPLEMENTED",
                "message": (
                    "Password reset not yet implemented. "
                    "TODO: Add token validation and email sending."
                ),
                "status": 501,
            }
        },
    )
