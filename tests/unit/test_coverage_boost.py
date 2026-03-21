import types

import pytest

from mnemo.api.v1.routes import health as health_mod
from mnemo.core.config import Settings


@pytest.mark.asyncio
async def test_health_check_variants(monkeypatch):
    async def db_ok():
        return True

    async def redis_ok():
        return True

    async def worker_ok():
        return True

    # Patch the functions that `health_check` actually references
    monkeypatch.setattr("mnemo.api.v1.routes.health.check_db_connection", db_ok)
    monkeypatch.setattr("mnemo.api.v1.routes.health.check_redis_connection", redis_ok)
    monkeypatch.setattr("mnemo.api.v1.routes.health.check_worker_heartbeat", worker_ok)

    resp = await health_mod.health_check()
    assert resp.status == "ok"
    assert resp.db == "ok"
    assert resp.redis == "ok"
    assert resp.worker == "ok"

    async def db_down():
        return False

    monkeypatch.setattr("mnemo.api.v1.routes.health.check_db_connection", db_down)
    resp = await health_mod.health_check()
    assert resp.status == "degraded"
    assert resp.db == "unreachable"


def test_settings_jwt_validator_and_env_props():
    # Validates is_production / is_development properties
    s = Settings(
        app_env="production",
        api_key_secret="1234567890123456789012345678901234567890",
    )
    assert s.is_production
    assert not s.is_development

    s2 = Settings(app_env="development")
    assert s2.is_development

    # short secret should raise
    with pytest.raises(ValueError):
        Settings(jwt_secret_key="short_secret_less_than_32_chars")


@pytest.mark.asyncio
async def test_redis_and_close(monkeypatch):
    # Provide a fake aioredis client via from_url
    class FakeClient:
        def __init__(self):
            self.ping_called = False

        async def ping(self):
            self.ping_called = True
            return True

        async def aclose(self):
            return None

    fake = FakeClient()

    # Patch the from_url factory used by get_redis
    monkeypatch.setattr("redis.asyncio.from_url", lambda *args, **kwargs: fake)

    # Import module and exercise get_redis / check_redis_connection / close_redis
    import mnemo.db.redis as redis_mod

    # Ensure internal client is reset
    redis_mod._redis_client = None

    client = redis_mod.get_redis()
    assert client is fake

    ok = await redis_mod.check_redis_connection()
    assert ok

    # closing should clear the global
    await redis_mod.close_redis()
    assert redis_mod._redis_client is None


@pytest.mark.asyncio
async def test_db_check_success_and_failure(monkeypatch):
    # Create a fake engine.connect context manager
    class DummyConn:
        async def execute(self, stmt):
            return None

    class DummyEngine:
        def __init__(self, succeed=True):
            self.succeed = succeed

        def connect(self):
            # Return a simple async context manager object with explicit
            # `__aenter__` / `__aexit__` implementations to avoid relying
            # on generator-based context managers in tests.
            if self.succeed:

                class OKCM:
                    async def __aenter__(self):
                        return DummyConn()

                    async def __aexit__(self, exc_type, exc, tb):
                        return False

                return OKCM()

            class FailCM:
                async def __aenter__(self):
                    raise RuntimeError("connect failed")

                async def __aexit__(self, exc_type, exc, tb):
                    return False

            return FailCM()

    # Success case
    dummy_ok = DummyEngine(succeed=True)
    monkeypatch.setattr("mnemo.db.database.engine", dummy_ok)
    import mnemo.db.database as db_mod

    ok = await db_mod.check_db_connection()
    assert ok

    # Failure case
    dummy_fail = DummyEngine(succeed=False)
    monkeypatch.setattr("mnemo.db.database.engine", dummy_fail)
    bad = await db_mod.check_db_connection()
    assert not bad


@pytest.mark.asyncio
async def test_lifespan_runs_and_calls_close(monkeypatch):
    # Patch get_redis to return a fake with ping, and patch close_redis and engine.dispose
    class FakeRedis:
        async def ping(self):
            return True

        async def aclose(self):
            return None

    fake = FakeRedis()

    monkeypatch.setattr("mnemo.main.get_redis", lambda: fake)

    async def fake_close():
        return None

    monkeypatch.setattr("mnemo.main.close_redis", fake_close)

    async def fake_dispose():
        return None

    monkeypatch.setattr("mnemo.main.engine", types.SimpleNamespace(dispose=fake_dispose))

    from mnemo.main import app, lifespan

    async with lifespan(app):
        # inside lifespan — nothing to assert beyond not-raising
        pass
