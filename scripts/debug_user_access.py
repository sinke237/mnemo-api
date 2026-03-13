import asyncio
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timezone

from mnemo.main import app
from mnemo.api.dependencies import get_current_user_from_token
from mnemo.core.constants import PermissionScope
from mnemo.models.user import User

async def run():
    target = User(
        id="usr_a1b2c3d4e5f6a7b8",
        display_name="Target User",
        country="US",
        locale="en-US",
        timezone="America/New_York",
        education_level=None,
        preferred_language="en",
        daily_goal_cards=20,
    )
    target.created_at = datetime.now(timezone.utc)

    admin_user = User(
        id="usr_deadbeefcafebabe",
        display_name="Admin",
        country="US",
        locale="en-US",
        timezone="America/New_York",
        education_level=None,
        preferred_language="en",
        daily_goal_cards=20,
    )
    admin_user.token_scopes = [PermissionScope.ADMIN.value]
    admin_user.created_at = datetime.now(timezone.utc)

    # fake service
    import mnemo.services.user as user_service

    async def fake_get_user_by_id(db, user_id):
        return target

    original_get_user_by_id = user_service.get_user_by_id
    try:
        app.dependency_overrides[get_current_user_from_token] = lambda: admin_user
        user_service.get_user_by_id = fake_get_user_by_id

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"/v1/users/{target.id}")
            print('status:', resp.status_code)
            try:
                print('json:', resp.json())
            except Exception as e:
                print('raw text:', resp.text)
    except ValueError as e:
        print(f"ValueError: {e}")
    finally:
        app.dependency_overrides.clear()
        user_service.get_user_by_id = original_get_user_by_id

if __name__ == '__main__':
    asyncio.run(run())
