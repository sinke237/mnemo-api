"""
Mnemo Learning API — main application entry point.

Initialises FastAPI, registers middleware, mounts routers,
and handles application lifecycle events.
"""

import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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


@app.exception_handler(FastAPIHTTPException)
async def http_exception_handler(request: Request, exc: FastAPIHTTPException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    if request_id is None:
        request_id = f"req_{uuid.uuid4().hex[:8]}"
    # Normalize FastAPIHTTPException detail to top-level {"error": ...} shape.
    detail = exc.detail
    if isinstance(detail, dict):
        if "error" in detail and isinstance(detail["error"], dict):
            error = detail["error"]
        else:
            # Preserve structured dict details by using it directly as the error
            error = detail
    else:
        error = {"message": str(detail)}

    # Ensure request_id present in response body
    error.setdefault("request_id", request_id)

    return JSONResponse(
        status_code=exc.status_code,
        content={"error": error},
        headers={"X-Request-ID": request_id},
    )


# ── Routers ────────────────────────────────────────────────────────────────────

app.include_router(v1_router)


# ── Root ───────────────────────────────────────────────────────────────────────


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {"message": "Mnemo Learning API v1. See /docs for the API reference."}
