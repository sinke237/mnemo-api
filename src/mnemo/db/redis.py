"""
Redis connection management.
Used for rate limiting, job queues, and session caching.

Note: redis.asyncio lacks complete type stubs. This module is excluded
from strict mypy checking via pyproject.toml [[tool.mypy.overrides]].
"""

from typing import Any

import redis.asyncio as aioredis

from mnemo.core.config import get_settings

settings = get_settings()

_redis_client: Any = None


def get_redis() -> Any:
    """
    Returns the shared Redis client instance.
    Initialised once at application startup.
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(  # type: ignore[no-untyped-call]
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def check_redis_connection() -> bool:
    """
    Health check: verify Redis is reachable and responsive.
    Returns True if healthy, False otherwise.
    """
    try:
        client = get_redis()
        await client.ping()
        return True
    except Exception:
        return False


async def close_redis() -> None:
    """Close the Redis connection on application shutdown."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
