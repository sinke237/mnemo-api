# pragma: no cover
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from mnemo.core.config import get_settings
from mnemo.core.constants import ErrorCode


class InputSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject oversized requests based on Content-Length header.

    Endpoints that accept large uploads (e.g., CSV import) already validate
    size explicitly and read the raw stream themselves. This middleware is a
    general guard for JSON/form payloads.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self.settings = get_settings()

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Allow the explicit import endpoints (`/v1/import` and any sub-path)
        # to handle large uploads themselves. Avoid overly permissive matches
        # like `/v1/importfoo` by requiring either exact match or a trailing '/'.
        path = request.url.path
        if path == "/v1/import" or path.startswith("/v1/import/"):
            return await call_next(request)
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
            except ValueError:
                # Malformed Content-Length header — reject with 400 Bad Request.
                request_id = getattr(request.state, "request_id", f"req_{uuid.uuid4().hex[:8]}")
                body = {
                    "error": {
                        "code": ErrorCode.VALIDATION_ERROR.value,
                        "message": "Invalid Content-Length header",
                        "status": 400,
                        "request_id": request_id,
                    }
                }
                headers = {"X-Request-ID": request_id}
                return JSONResponse(status_code=400, content=body, headers=headers)
            if size > self.settings.max_request_body_bytes:
                request_id = getattr(request.state, "request_id", f"req_{uuid.uuid4().hex[:8]}")
                body = {
                    "error": {
                        "code": ErrorCode.VALIDATION_ERROR.value,
                        "message": "Request body too large",
                        "status": 413,
                        "request_id": request_id,
                    }
                }
                headers = {"X-Request-ID": request_id}
                return JSONResponse(status_code=413, content=body, headers=headers)

        response = await call_next(request)
        return response
