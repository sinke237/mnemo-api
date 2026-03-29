"""
Authentication routes.
Handles JWT token generation with email-based login.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.core.config import get_settings
from mnemo.core.constants import ErrorCode
from mnemo.db.database import get_db
from mnemo.schemas.auth import LoginRequest, TokenRequest, TokenResponse
from mnemo.schemas.error import ErrorResponse
from mnemo.services import api_key as api_key_service
from mnemo.services import auth as auth_service
from mnemo.services import user as user_service

router = APIRouter(prefix="/auth", tags=["authentication"])
db_dep = Depends(get_db)
settings = get_settings()


@router.post(
    "/token",
    response_model=TokenResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid API key or user not found"},
        403: {"model": ErrorResponse, "description": "Insufficient scope"},
    },
    summary="Get JWT access token (API key authentication)",
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
    Generate a JWT access token using API key authentication.

    Returns 401 if API key is invalid or user not found.
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


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid credentials"},
    },
    summary="Email + password login",
    description=(
        "Authenticate with email + password and receive a short-lived JWT. "
        "Returns the same shape as POST /v1/auth/token so clients can use either "
        "interchangeably. Does NOT distinguish 'user not found' from 'wrong password' "
        "to prevent email enumeration."
    ),
)
async def login(
    request: LoginRequest,
    db: AsyncSession = db_dep,
) -> TokenResponse:
    """
    Authenticate a user by email + password and return a JWT access token.

    Security: always returns 401 'Invalid credentials' on failure — no enumeration.
    """
    user = await auth_service.authenticate_user_by_email(db, request.email, request.password)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": ErrorCode.INVALID_CREDENTIALS.value,
                    "message": "Invalid credentials",
                    "status": 401,
                }
            },
        )

    # Determine scopes based on the user's role; admin_access_granted is not
    # used for authentication/authorization (it gates consent, not role).
    scopes = auth_service.scopes_for_role(user.role)
    access_token = auth_service.create_access_token(user_id=user.id, scopes=scopes)

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.jwt_expiry_seconds,
        token_type="Bearer",  # noqa: S106
    )
