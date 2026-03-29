"""
API Key management routes.
Allows users to create, list, and revoke their own API keys.
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.api.dependencies import get_current_user_from_token
from mnemo.core.config import get_settings
from mnemo.core.constants import ErrorCode, PermissionScope
from mnemo.db.database import get_db
from mnemo.models.api_key import APIKey
from mnemo.models.user import User
from mnemo.schemas.error import ErrorResponse
from mnemo.schemas.user import (
    APIKeyListItem,
    CreateAPIKeyRequest,
    CreateAPIKeyResponse,
    ListAPIKeysResponse,
    RevokeAPIKeyResponse,
)
from mnemo.services import api_key as api_key_service
from mnemo.services import auth as auth_service

settings = get_settings()

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/user", tags=["user"])
db_dep = Depends(get_db)
current_user_dep = Depends(get_current_user_from_token)


@router.post(
    "/api-keys",
    status_code=201,
    response_model=CreateAPIKeyResponse,
    responses={
        201: {
            "description": "API key created; response includes plain API key and its type",
            "content": {
                "application/json": {
                    "example": {
                        "key_id": "key_a1b2c3d4e5f6g7h8",
                        "api_key": "mnm_test_examplekey",
                        "key_type": "test",
                        "name": "My Key",
                        "scopes": ["decks:read", "decks:write"],
                        "created_at": "2026-03-29T12:00:00Z",
                    }
                }
            },
        },
        401: {"model": ErrorResponse, "description": "Invalid or expired token"},
        403: {
            "model": ErrorResponse,
            "description": (
                "Live API key creation is restricted. To create a live key, the deployment must "
                "enable self-service (ALLOW_LIVE_KEYS=true) "
                "and your email address must be verified."
            ),
        },
    },
    summary="Create a new API key",
    description=(
        "Create a new API key (test or live) for the authenticated user. "
        "The plain API key is shown ONCE — store it immediately."
        " The key inherits the user's role-based scopes.\n\n"
        "If `is_live=true` is requested, the server requires that the deployment has enabled "
        "self-service live keys and that the user's email is verified; otherwise a 403 is returned."
    ),
)
async def create_api_key(
    request: CreateAPIKeyRequest,
    current_user: User = current_user_dep,
    db: AsyncSession = db_dep,
) -> CreateAPIKeyResponse:
    """Create a new API key for the authenticated user."""

    # Get scopes based on user role
    scopes_list = auth_service.scopes_for_role(current_user.role)

    scopes = [PermissionScope(s) for s in scopes_list]

    # Create the API key
    # Guard live key creation behind deployment flag + verified email
    if request.is_live:
        if not settings.allow_live_keys:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": {
                        "code": ErrorCode.INSUFFICIENT_SCOPE.value,
                        "message": "Live API key creation is disabled in this deployment",
                        "status": 403,
                    }
                },
            )

        if not current_user.email_verified:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": {
                        "code": ErrorCode.INSUFFICIENT_SCOPE.value,
                        "message": "Email address must be verified before creating a live API key",
                        "status": 403,
                    }
                },
            )

    api_key_record, plain_key = await api_key_service.create_api_key(
        db=db,
        user_id=current_user.id,
        name=request.name,
        is_live=request.is_live,
        scopes=scopes,
    )

    key_type = "live" if request.is_live else "test"

    return CreateAPIKeyResponse(
        key_id=api_key_record.id,
        api_key=plain_key,
        key_type=key_type,
        name=api_key_record.name,
        scopes=scopes_list,
        created_at=api_key_record.created_at,
    )


@router.get(
    "/api-keys",
    response_model=ListAPIKeysResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or expired token"},
    },
    summary="List your API keys",
    description=(
        "Returns a list of all API keys for the authenticated user "
        "(without showing the actual keys)."
    ),
)
async def list_api_keys(
    current_user: User = current_user_dep,
    db: AsyncSession = db_dep,
) -> ListAPIKeysResponse:
    """List all API keys for the authenticated user."""

    result = await db.execute(
        select(APIKey).where(APIKey.user_id == current_user.id).order_by(APIKey.created_at.desc())
    )
    keys = result.scalars().all()

    items = []
    for key in keys:
        scopes_parsed: list[str] = []
        if key.scopes:
            try:
                parsed = json.loads(key.scopes)
                if isinstance(parsed, list):
                    # Keep only string items; ignore invalid/non-string entries
                    scopes_parsed = [s for s in parsed if isinstance(s, str)]
                else:
                    scopes_parsed = []
            except (json.JSONDecodeError, ValueError, TypeError):
                scopes_parsed = []

        items.append(
            APIKeyListItem(
                key_id=key.id,
                name=key.name,
                key_type="live" if key.is_live else "test",
                key_hint=key.key_hint,
                scopes=scopes_parsed,
                is_active=key.is_active,
                created_at=key.created_at,
                last_used_at=key.last_used_at,
            )
        )

    return ListAPIKeysResponse(keys=items)


@router.delete(
    "/api-keys/{key_id}",
    response_model=RevokeAPIKeyResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or expired token"},
        403: {"model": ErrorResponse, "description": "Cannot revoke another user's API key"},
        404: {"model": ErrorResponse, "description": "API key not found"},
    },
    summary="Revoke an API key",
    description=(
        "Permanently revoke an API key. The key will no longer be usable " "for authentication."
    ),
)
async def revoke_api_key(
    key_id: str,
    current_user: User = current_user_dep,
    db: AsyncSession = db_dep,
) -> RevokeAPIKeyResponse:
    """Revoke an API key belonging to the authenticated user."""

    # Fetch the API key
    result = await db.execute(select(APIKey).where(APIKey.id == key_id))
    api_key = result.scalar_one_or_none()

    if api_key is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": ErrorCode.API_KEY_NOT_FOUND.value,
                    "message": "API key not found",
                    "status": 404,
                }
            },
        )

    # Verify ownership
    if api_key.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": ErrorCode.INSUFFICIENT_SCOPE.value,
                    "message": "Cannot revoke another user's API key",
                    "status": 403,
                }
            },
        )

    # Revoke the key
    success = await api_key_service.revoke_api_key(db, key_id)

    if not success:
        logger.warning(
            "api_key_service.revoke_api_key returned False for key_id=%s user_id=%s",
            key_id,
            current_user.id,
        )
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": ErrorCode.API_KEY_NOT_FOUND.value,
                    "message": "API key not found",
                    "status": 404,
                }
            },
        )

    # Refresh to get updated revoked_at timestamp
    await db.refresh(api_key)

    return RevokeAPIKeyResponse(
        key_id=api_key.id,
        revoked_at=api_key.revoked_at,
    )
