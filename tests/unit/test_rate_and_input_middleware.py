import importlib
import json
import sys

import pytest
from httpx import ASGITransport, AsyncClient

from tests.helpers.fake_redis import FakeRedis


@pytest.fixture(autouse=True)
def reset_settings_after_test() -> None:
    """Ensure settings cache is cleared and module reloaded after each test."""
    yield
    from mnemo.core.config import get_settings

    get_settings.cache_clear()
    if "mnemo.main" in sys.modules:
        importlib.reload(sys.modules["mnemo.main"])


@pytest.mark.asyncio
async def test_rate_limit_per_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRedis()

    # Monkeypatch Redis and set low read limit via middleware method override
    # Ensure the app's existing redis client is replaced before app import
    import mnemo.db.redis as redis_mod

    redis_mod._redis_client = fake
    monkeypatch.setattr("mnemo.db.redis.get_redis", lambda: fake)

    # Clear the settings cache and modify settings BEFORE importing the app
    from mnemo.core.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    settings.rate_limit_read_per_minute = 2

    # Force reload of mnemo.main to ensure middleware is re-instantiated with new settings
    if "mnemo.main" in sys.modules:
        importlib.reload(sys.modules["mnemo.main"])

    from mnemo.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {
            "x-api-key": "mnm_test_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        }
        r1 = await ac.get("/v1/health", headers=headers)
        r2 = await ac.get("/v1/health", headers=headers)
        r3 = await ac.get("/v1/health", headers=headers)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429
    assert "X-RateLimit-Limit" in r1.headers
    assert "X-RateLimit-Remaining" in r1.headers
    assert "Retry-After" in r3.headers
    # body includes request_id
    body = r3.json()
    assert "error" in body
    assert body["error"].get("request_id") is not None


@pytest.mark.asyncio
async def test_input_size_limit_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    # Small max size
    # Ensure app uses a fake redis client (health check and rate middleware)
    fake2 = FakeRedis()
    import mnemo.db.redis as redis_mod2

    redis_mod2._redis_client = fake2
    monkeypatch.setattr("mnemo.db.redis.get_redis", lambda: fake2)

    # Clear the settings cache and modify settings BEFORE importing the app
    from mnemo.core.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    settings.max_request_body_bytes = 10

    # Provide fake API key dependency with admin scope so POST /v1/users can run

    class DummyKey:
        scopes = json.dumps(["admin"])

    monkeypatch.setattr("mnemo.api.dependencies.get_api_key_from_header", lambda: DummyKey())

    # Force reload of mnemo.main to ensure middleware is re-instantiated with new settings
    if "mnemo.main" in sys.modules:
        importlib.reload(sys.modules["mnemo.main"])

    from mnemo.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = {"content-length": "1024", "x-api-key": "mnm_test_dummy"}
        # POST to create user should be blocked by middleware before body parsing
        resp = await ac.post(
            "/v1/users",
            headers=headers,
            json={
                "display_name": "A",
                "country": "US",
                "preferred_language": "en",
                "daily_goal_cards": 1,
            },
        )

    assert resp.status_code == 413
    body = resp.json()
    assert "error" in body
    assert body["error"].get("request_id") is not None
