import importlib
import sys

import pytest
from httpx import ASGITransport, AsyncClient

from tests.helpers.fake_redis import FakeRedis


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
    # Ensure middleware is re-instantiated with new settings
    if "mnemo.main" in sys.modules:
        importlib.reload(sys.modules["mnemo.main"])

    from mnemo.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"x-api-key": "mnm_test_key_for_get"}
        r1 = await ac.get("/v1/sessions/nonexistent", headers=headers)
        r2 = await ac.get("/v1/sessions/nonexistent", headers=headers)

    # First request should not be a 429
    assert r1.status_code != 429
    # Second request should be rate-limited
    assert r2.status_code == 429
    assert "X-RateLimit-Limit" in (r1.headers or {})
    assert "X-RateLimit-Remaining" in (r1.headers or {})


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
    # Ensure middleware is re-instantiated with new settings
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
    assert "X-RateLimit-Limit" in (r1.headers or {})
    assert "X-RateLimit-Remaining" in (r1.headers or {})
