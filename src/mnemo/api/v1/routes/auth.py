"""
Authentication routes.
Handles JWT token generation per spec section 02: Authentication.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.core.config import get_settings
from mnemo.core.constants import ErrorCode
from mnemo.db.database import get_db
from mnemo.schemas.auth import TokenRequest, TokenResponse
from mnemo.schemas.error import ErrorResponse
from mnemo.services import api_key as api_key_service
from mnemo.services import auth as auth_service
from mnemo.services import user as user_service

router = APIRouter(prefix="/auth", tags=["authentication"])
# module-level Depends singleton to satisfy ruff B008
db_dep = Depends(get_db)
settings = get_settings()


@router.post(
    "/token",
    response_model=TokenResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid API key or user not found"},
        403: {"model": ErrorResponse, "description": "Insufficient scope"},
    },
    summary="Get JWT access token",
    description=(
        "Exchange an API key and user_id for a short-lived JWT token. "
        "Tokens expire after 1 hour and must be refreshed by calling this endpoint again. "
        "The token inherits the scopes from the API key used to generate it."
    ),
)
async def get_access_token(
    request: TokenRequest,
    db: AsyncSession = db_dep,
) -> TokenResponse:
    """
    Generate a JWT access token.
    Per spec:
    - Requires valid API key and existing user_id
    - Token expires after JWT_EXPIRY_SECONDS (default 3600 = 1 hour)
    - Token scopes cannot exceed API key scopes
    - Returns 401 if API key is invalid or user not found
    """
    # Validate API key
    api_key = await api_key_service.validate_api_key(db, request.api_key)

    if api_key is None:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": ErrorCode.INVALID_API_KEY.value,
                    "message": "Invalid or revoked API key",
                    "status": 401,
                }
            },
        )

    # Verify user exists
    user_exists = await user_service.user_exists(db, request.user_id)

    if not user_exists:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": ErrorCode.USER_NOT_FOUND.value,
                    "message": "User not found",
                    "status": 401,
                }
            },
        )

    # Verify API key belongs to this user
    if api_key.user_id != request.user_id:
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": ErrorCode.API_KEY_OWNER_MISMATCH.value,
                    "message": "API key does not belong to this user",
                    "status": 403,
                }
            },
        )

    # Get scopes from API key
    scopes = api_key_service.get_key_scopes(api_key)

    # Generate JWT token
    access_token = auth_service.create_access_token(
        user_id=request.user_id,
        scopes=scopes,
    )

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.jwt_expiry_seconds,
        token_type="Bearer",  # noqa: S106
    )
