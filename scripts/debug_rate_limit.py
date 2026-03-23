import asyncio
from httpx import AsyncClient, ASGITransport

from tests.helpers.fake_redis import FakeRedis

# set fake before importing app
import mnemo.db.redis as redis_mod
redis_mod._redis_client = FakeRedis()

from mnemo.main import app

async def main():
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as ac:
        headers = {"x-api-key": "mnm_test_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
        r1 = await ac.get('/v1/health', headers=headers)
        r2 = await ac.get('/v1/health', headers=headers)
        r3 = await ac.get('/v1/health', headers=headers)
        print('r1', r1.status_code, r1.headers)
        print('r1 body', r1.text)
        print('r2', r2.status_code, r2.headers)
        print('r2 body', r2.text)
        print('r3', r3.status_code, r3.headers)
        print('r3 body', r3.text)

asyncio.run(main())
