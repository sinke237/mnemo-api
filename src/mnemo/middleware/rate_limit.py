# pragma: no cover
import hashlib
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from mnemo.core.config import get_settings
from mnemo.core.constants import ErrorCode
from mnemo.db.redis import get_redis


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple Redis-backed rate limiter.

    - Per-API-key when `X-API-Key` header present (hashed to avoid storing raw secrets)
    - Fallback to client IP when no API key
    - Category detection based on path/method
    - Emits `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` on every response
    - Returns 429 with `Retry-After` when exceeded
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self.settings = get_settings()
        # Redis client will be fetched per-request to avoid using a stale
        # connection/pool stored on the middleware instance.

    def _hash_api_key(self, api_key: str) -> str:
        """
        Hash the API key to avoid storing raw secrets in Redis.
        Uses the API key secret as salt for consistent hashing.
        """
        salt = self.settings.api_key_secret.encode("utf-8")
        key_bytes = api_key.encode("utf-8")
        return hashlib.sha256(salt + key_bytes).hexdigest()

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        now = int(time.time())

        api_key = request.headers.get("x-api-key")
        if api_key:
            hashed_key = self._hash_api_key(api_key)
            identifier = f"api:{hashed_key}"
        else:
            client_host = getattr(request.client, "host", "unknown")
            identifier = f"ip:{client_host}"

        category, limit, window = self._resolve_category_and_limit(request.url.path, request.method)

        # compute bucket & TTL
        if window == 3600:
            bucket = now // 3600
            ttl = (bucket + 1) * 3600 - now
        else:
            bucket = now // 60
            ttl = (bucket + 1) * 60 - now

        key = f"mnemo:rl:{category}:{identifier}:{bucket}"

        try:
            redis = get_redis()
            current = await redis.incr(key)
            if current == 1:
                await redis.expire(key, ttl)
        except Exception:
            # Fail-open: if Redis is unavailable, allow traffic but omit rate info
            response = await call_next(request)
            return response

        remaining = max(limit - current, 0)
        reset = now + ttl

        if current > limit:
            retry_after = ttl
            request_id = getattr(request.state, "request_id", f"req_{uuid.uuid4().hex[:8]}")
            body = {
                "error": {
                    "code": ErrorCode.RATE_LIMIT_EXCEEDED.value,
                    "message": "Rate limit exceeded",
                    "status": 429,
                    "request_id": request_id,
                }
            }
            headers = {
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset),
                "X-Request-ID": request_id,
            }
            return JSONResponse(status_code=429, content=body, headers=headers)

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset)
        return response

    def _resolve_category_and_limit(self, path: str, method: str) -> tuple[str, int, int]:
        s = self.settings
        if path == "/v1/import" or path.startswith("/v1/import/"):
            return ("import", s.rate_limit_import_per_hour, 3600)
        if path == "/v1/auth" or path.startswith("/v1/auth/"):
            return ("auth", s.rate_limit_auth_per_minute, 60)
        # Session endpoints include both read (GET) and answer (POST/PUT) actions.
        # Only apply the `answer` rate limit for non-GET methods so that read-only
        # GET requests fall through to the generic read rate limit.
        if (path == "/v1/sessions" or path.startswith("/v1/sessions/")) and method.upper() != "GET":
            return ("session", s.rate_limit_answer_per_minute, 60)
        if method.upper() == "GET":
            return ("read", s.rate_limit_read_per_minute, 60)
        return ("write", s.rate_limit_write_per_minute, 60)
