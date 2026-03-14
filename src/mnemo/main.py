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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from mnemo.api.v1.router import router as v1_router
from mnemo.core.config import get_settings
from mnemo.db.database import engine
from mnemo.db.redis import close_redis, get_redis

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


@app.middleware("http")
async def add_request_id(request: Request, call_next: CallNext) -> Response:
    """
    Attach a unique request_id to every request.
    Included in all error responses per NFR-05.2.
    """
    request_id = f"req_{uuid.uuid4().hex[:8]}"
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# ── Routers ────────────────────────────────────────────────────────────────────

app.include_router(v1_router)


# ── Root ───────────────────────────────────────────────────────────────────────


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {"message": "Mnemo Learning API v1. See /docs for the API reference."}
