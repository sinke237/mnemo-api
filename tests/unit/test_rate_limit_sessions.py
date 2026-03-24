import importlib
import logging
import sys

import pytest
from httpx import ASGITransport, AsyncClient

from tests.helpers.fake_redis import FakeRedis


@pytest.fixture(autouse=True)
def reset_settings_after_test():
    """Reset Redis client and settings cache after each test.

    Reset `redis_mod._redis_client` and `get_settings.cache_clear()` then
    reload `mnemo.main` so the app is reinitialized for subsequent tests.
    """
    yield
    # Reset Redis client
    import mnemo.db.redis as redis_mod

    redis_mod._redis_client = None
    # Clear settings cache
    from mnemo.core.config import get_settings

    get_settings.cache_clear()
    # Reload mnemo.main to re-initialize the app/module state
    import importlib

    try:
        import mnemo.main as mnemo_main

        importlib.reload(mnemo_main)
    except Exception as e:
        # Best-effort reload; log the failure so test failures aren't silently ignored.
        logging.exception("Failed to reload mnemo.main during fixture teardown: %s", e)


@pytest.mark.asyncio
async def test_sessions_get_uses_read_limit(monkeypatch):
    fake = FakeRedis()
    import mnemo.db.redis as redis_mod

    redis_mod._redis_client = fake
    monkeypatch.setattr("mnemo.db.redis.get_redis", lambda: fake)

    # Clear settings cache and set low read limit
    from mnemo.core.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    settings.rate_limit_read_per_minute = 1
    # Reload required here to re-instantiate middleware with modified settings.
    # This is distinct from the fixture's post-test reload which resets to defaults.
    if "mnemo.main" in sys.modules:
        importlib.reload(sys.modules["mnemo.main"])

    from mnemo.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"x-api-key": "mnm_test_key_for_get"}
        r1 = await ac.get("/v1/sessions/nonexistent", headers=headers)
        r2 = await ac.get("/v1/sessions/nonexistent", headers=headers)

    # First request should not be a 429 (endpoint may return 401/404 in unit tests)
    assert r1.status_code != 429
    # Second request should be rate-limited
    assert r2.status_code == 429
    assert "X-RateLimit-Limit" in r1.headers
    assert "X-RateLimit-Remaining" in r1.headers


@pytest.mark.asyncio
async def test_sessions_post_uses_answer_limit(monkeypatch):
    fake = FakeRedis()
    import mnemo.db.redis as redis_mod

    redis_mod._redis_client = fake
    monkeypatch.setattr("mnemo.db.redis.get_redis", lambda: fake)

    # Clear settings cache and set low answer limit
    from mnemo.core.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    settings.rate_limit_answer_per_minute = 1
    settings.rate_limit_read_per_minute = 1000
    # Reload required here to re-instantiate middleware with modified settings.
    # This is distinct from the fixture's post-test reload which resets to defaults.
    if "mnemo.main" in sys.modules:
        importlib.reload(sys.modules["mnemo.main"])

    from mnemo.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"x-api-key": "mnm_test_key_for_post"}
        # POST to answer endpoint - body omitted; middleware runs before route handlers
        r1 = await ac.post("/v1/sessions/abc/answer", headers=headers, json={"answer": "a"})
        r2 = await ac.post("/v1/sessions/abc/answer", headers=headers, json={"answer": "a"})

    assert r1.status_code != 429
    assert r2.status_code == 429
    assert "X-RateLimit-Limit" in r1.headers
    assert "X-RateLimit-Remaining" in r1.headers
