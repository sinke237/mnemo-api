import asyncio
from httpx import AsyncClient, ASGITransport

from mnemo.main import app
from mnemo.api.dependencies import get_current_user_from_token
from mnemo.models.user import User
from datetime import datetime

async def run():
    target = User(
        id="usr_b1b2c3d4e5f6a7b8",
        display_name="Target 2",
        country="US",
        locale="en-US",
        timezone="America/New_York",
        education_level=None,
        preferred_language="en",
        daily_goal_cards=20,
    )
    target.created_at = datetime.utcnow()

    user = User(
        id="usr_feedfacecafef00d",
        display_name="Normal",
        country="US",
        locale="en-US",
        timezone="America/New_York",
        education_level=None,
        preferred_language="en",
        daily_goal_cards=20,
    )
    user.token_scopes = []
    user.created_at = datetime.utcnow()

    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user_from_token] = lambda: user

    import mnemo.services.user as user_service

    def fake_get_user_by_id(db, user_id):
        return target

    user_service.get_user_by_id = fake_get_user_by_id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get(f"/v1/users/{target.id}")
        print('status:', resp.status_code)
        try:
            print('json:', resp.json())
        except Exception:
            print('text:', resp.text)

if __name__ == '__main__':
    asyncio.run(run())
