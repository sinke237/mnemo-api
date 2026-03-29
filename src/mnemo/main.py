"""
Mnemo Learning API — main application entry point.

Initialises FastAPI, registers middleware, mounts routers,
and handles application lifecycle events.
"""

import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable, Mapping, Sequence
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from mnemo.api.v1.router import router as v1_router
from mnemo.core.config import get_settings
from mnemo.db.database import engine
from mnemo.db.redis import close_redis, get_redis
from mnemo.middleware.input_limits import InputSizeLimitMiddleware
from mnemo.middleware.rate_limit import RateLimitMiddleware

logger = structlog.get_logger()
settings = get_settings()

# Type alias for ASGI middleware call_next
CallNext = Callable[[Request], Awaitable[Response]]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Handle application startup and shutdown."""
    logger.info("mnemo_api_starting", env=settings.app_env, version="1.0.0")
    try:
        redis = get_redis()
        await redis.ping()
        logger.info("redis_connected")
    except Exception as e:
        logger.error("redis_connection_failed", error=str(e))
    logger.info("mnemo_api_ready")

    yield

    logger.info("mnemo_api_shutting_down")
    await close_redis()
    await engine.dispose()
    logger.info("mnemo_api_shutdown_complete")


app = FastAPI(
    title="Mnemo Learning API",
    description="Spaced repetition and active recall, delivered as a developer API.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    openapi_url="/openapi.json" if not settings.is_production else None,
)

# ── Middleware ─────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_development else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def enforce_https_in_production(request: Request, call_next: CallNext) -> Response:
    """Reject plain HTTP in production. Per spec: HTTP_NOT_ALLOWED → 403."""
    if settings.is_production and request.url.scheme == "http":
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "HTTP_NOT_ALLOWED",
                    "message": "All requests must use HTTPS.",
                    "status": 403,
                }
            },
        )
    return await call_next(request)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Attach a unique request_id to every request.
    Included in all error responses per NFR-05.2.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = f"req_{uuid.uuid4().hex[:8]}"
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# Register middlewares in reverse order of execution.
# add_middleware() inserts at the beginning, so the last one added runs first.
# Order of execution: RequestID → RateLimit → InputSizeLimit → app
app.add_middleware(InputSizeLimitMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestIDMiddleware)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler to ensure every error response contains a request id."""
    request_id = getattr(request.state, "request_id", None)
    if request_id is None:
        request_id = f"req_{uuid.uuid4().hex[:8]}"
    logger.exception("unhandled_exception", error=str(exc), request_id=request_id)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Internal server error",
                "status": 500,
                "request_id": request_id,
            }
        },
        headers={"X-Request-ID": request_id},
    )


# Centralized HTTP error normalization
_DetailType = Mapping[str, object] | Sequence[object] | str | int | float | None


def _normalize_error_detail(
    request: Request, detail: _DetailType, status: int
) -> dict[str, object]:
    request_id = getattr(request.state, "request_id", None) or f"req_{uuid.uuid4().hex[:8]}"

    # Preserve structured dict details where possible
    if isinstance(detail, dict):
        if "error" in detail and isinstance(detail["error"], dict):
            error = dict(detail["error"])  # copy to avoid mutating original
        else:
            error = dict(detail)
    elif isinstance(detail, list):
        error = {"message": "Validation error", "detail": detail}
    else:
        error = {"message": str(detail)}

    # Derive canonical code
    code = None
    if isinstance(error, dict):
        code = error.get("code")

    if not code:
        canonical = {
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            422: "VALIDATION_ERROR",
            500: "INTERNAL_ERROR",
            403: "HTTP_NOT_ALLOWED",
        }
        code = canonical.get(int(status), f"HTTP_{int(status)}")

    # Ensure fields
    error["code"] = str(code)
    error["message"] = str(error.get("message", ""))
    error["status"] = int(status)
    error["request_id"] = request_id

    return error


def _build_response_from_exception(
    request: Request, exc: Exception, status: int, detail: _DetailType
) -> JSONResponse:
    # Merge headers instead of replacing them
    exc_headers = getattr(exc, "headers", None) or {}
    error = _normalize_error_detail(request, detail, status)
    request_id = error["request_id"]
    headers = {**exc_headers, "X-Request-ID": request_id}
    return JSONResponse(status_code=int(status), content={"error": error}, headers=headers)


@app.exception_handler(FastAPIHTTPException)
async def fastapi_http_exception_handler(
    request: Request, exc: FastAPIHTTPException
) -> JSONResponse:
    return _build_response_from_exception(
        request, exc, getattr(exc, "status_code", 500), exc.detail
    )


@app.exception_handler(StarletteHTTPException)
async def starlette_http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    return _build_response_from_exception(
        request, exc, getattr(exc, "status_code", 500), exc.detail
    )


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # RequestValidationError doesn't always carry a status_code attribute
    status = getattr(exc, "status_code", 422)
    # Preserve the validation errors list if available
    detail = getattr(exc, "errors", None)
    if callable(detail):
        detail = exc.errors()
    if detail is None:
        detail = getattr(exc, "detail", str(exc))
    # Sanitize: Pydantic v2 errors() may include non-serializable objects
    # (e.g. ValueError in ctx). Convert ctx values to strings.
    if isinstance(detail, list):
        for err in detail:
            if isinstance(err, dict):
                ctx = err.get("ctx")
                if isinstance(ctx, dict):
                    err["ctx"] = {k: str(v) for k, v in ctx.items()}
    return _build_response_from_exception(request, exc, status, detail)


# ── Routers ────────────────────────────────────────────────────────────────────

app.include_router(v1_router)


# ── Root ───────────────────────────────────────────────────────────────────────


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {"message": "Mnemo Learning API v1. See /docs for the API reference."}
