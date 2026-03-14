"""FastAPI authentication dependencies.

Provides helper dependencies used across API routes:
- `get_api_key_from_header` — validate `X-API-Key` header
- `get_current_user_from_token` — validate `Authorization: Bearer <token>`
- `require_scope(scope)` — factory returning a dependency that enforces API key scopes
- `require_user_scope(scope)` — factory returning a dependency that enforces JWT token scopes

Module uses module-level dependency singletons to avoid ruff B008.
"""

from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.core.constants import ErrorCode, PermissionScope
from mnemo.db.database import get_db
from mnemo.models.api_key import APIKey
from mnemo.models.user import User
from mnemo.services import api_key as api_key_service
from mnemo.services import auth as auth_service
from mnemo.services import user as user_service

# Module-level dependency singletons (avoid calling Depends() inside function defaults)
db_dep = Depends(get_db)
# HTTPBearer registers the OpenAPI BearerAuth security scheme so that the
# /docs UI "Authorize" button populates the Authorization header correctly.
# scheme_name='bearerAuth' uses the conventional name Swagger UI recognises.
_bearer_scheme = HTTPBearer(auto_error=False, scheme_name="bearerAuth")
auth_header_dep = Depends(_bearer_scheme)


async def get_api_key_from_header(
    x_api_key: str | None = Header(default=None),
    db: AsyncSession = db_dep,
) -> APIKey:
    """Validate the `X-API-Key` header and return the APIKey record.

    Raises 401 when missing/invalid or revoked.
    """
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": ErrorCode.INVALID_API_KEY.value,
                    "message": "Missing API key",
                    "status": 401,
                }
            },
        )

    api_key = await api_key_service.validate_api_key(db, x_api_key)

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

    return api_key


async def get_current_user_from_token(
    credentials: HTTPAuthorizationCredentials | None = auth_header_dep,
    db: AsyncSession = db_dep,
) -> User:
    """Validate `Authorization: Bearer <token>` and return the User record.

    Raises 401 on missing/invalid/expired token and 401 if user not found.
    """
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": ErrorCode.INVALID_TOKEN.value,
                    "message": "Missing or invalid Authorization header",
                    "status": 401,
                }
            },
        )

    token = credentials.credentials

    payload, token_error = auth_service.decode_access_token_with_error(token)
    if payload is None:
        is_expired = token_error == "expired"  # noqa: S105
        error_code = ErrorCode.TOKEN_EXPIRED.value if is_expired else ErrorCode.INVALID_TOKEN.value
        message = "Token expired" if is_expired else "Invalid token"
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": error_code,
                    "message": message,
                    "status": 401,
                }
            },
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": ErrorCode.INVALID_TOKEN.value,
                    "message": "Malformed token (missing subject)",
                    "status": 401,
                }
            },
        )

    user = await user_service.get_user_by_id(db, user_id)

    if user is None:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": ErrorCode.INVALID_TOKEN.value,
                    "message": f"User not found: {user_id}",
                    "status": 401,
                }
            },
        )
    # Attach token scopes to the returned user instance so downstream
    # dependencies and route handlers can rely on scopes without re-parsing
    # the raw token.
    scopes = payload.get("scopes", [])
    if not isinstance(scopes, list) or not all(isinstance(scope, str) for scope in scopes):
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": ErrorCode.INVALID_TOKEN.value,
                    "message": "Invalid token scopes",
                    "status": 401,
                }
            },
        )

    # Attach a transient attribute to the SQLAlchemy model instance.
    # Direct attribute assignment is fine on ORM instances for transient data.
    user.token_scopes = scopes

    return user


# Module-level singleton referencing the callables above — used in factory deps below.
api_key_dep = Depends(get_api_key_from_header)


def require_scope(required_scope: PermissionScope) -> Callable[..., APIKey]:
    """Return a dependency that enforces an API key has `required_scope`.

    Usage: `dependencies=[Depends(require_scope(PermissionScope.ADMIN))]`
    """

    def _require(api_key: APIKey = api_key_dep) -> APIKey:
        if not api_key_service.has_scope(api_key, required_scope):
            raise HTTPException(
                status_code=403,
                detail={
                    "error": {
                        "code": ErrorCode.INSUFFICIENT_SCOPE.value,
                        "message": "Insufficient scope",
                        "status": 403,
                    }
                },
            )
        return api_key

    return _require


def require_user_scope(required_scope: PermissionScope) -> Callable[..., Coroutine[Any, Any, None]]:
    """Return a dependency that enforces a JWT token has `required_scope`.

    This dependency first validates the token and ensures the user exists by
    delegating to `get_current_user_from_token`. That function raises the
    appropriate 401/404 HTTPExceptions for missing/invalid/expired tokens or
    non-existent users. After authentication succeeds, we verify the token
    contains the required scope via `auth_service.token_has_scope`.
    """

    async def _require(
        credentials: HTTPAuthorizationCredentials | None = auth_header_dep,
        db: AsyncSession = db_dep,
    ) -> None:
        # Validate token and user existence (propagates 401/404 as needed)
        user = await get_current_user_from_token(credentials, db)

        # At this point the token is syntactically valid and the user exists.
        # Use the attached `token_scopes` attribute (transient) to enforce
        # the required scope without re-decoding the raw token.
        scopes = getattr(user, "token_scopes", []) or []

        # Admin scope grants all permissions
        if PermissionScope.ADMIN.value in scopes:
            return None

        if required_scope.value not in scopes:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": {
                        "code": ErrorCode.INSUFFICIENT_SCOPE.value,
                        "message": "Insufficient scope for this operation",
                        "status": 403,
                    }
                },
            )

    return _require
