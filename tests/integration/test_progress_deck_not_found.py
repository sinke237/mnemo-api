import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.core.constants import ErrorCode, PermissionScope
from mnemo.main import app
from mnemo.schemas.user import UserProvisionRequest as UserCreate
from mnemo.services.api_key import create_api_key
from mnemo.services.user import create_user


@pytest.mark.asyncio
async def test_deck_progress_not_found_returns_404(db_session: AsyncSession) -> None:
    user_data = UserCreate(
        email="deck-test@example.com",
        password="securePass123",
        display_name="Deck Test",
        country="US",
        timezone="America/New_York",
        locale="en-US",
        preferred_language="en",
        daily_goal_cards=10,
    )
    user = await create_user(db_session, user_data)

    # Create API key WITH PROGRESS_READ
    _, key_with_scope = await create_api_key(
        db=db_session,
        user_id=user.id,
        name="with-progress-key",
        is_live=False,
        scopes=[PermissionScope.PROGRESS_READ],
    )

    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token_resp = await client.post(
            "/v1/auth/token", json={"user_id": user.id, "api_key": key_with_scope}
        )
        assert token_resp.status_code == 200
        token = token_resp.json()["access_token"]

        # Use a deck id that doesn't exist
        resp = await client.get(
            f"/v1/users/{user.id}/progress/nonexistent_deck",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404
        payload = resp.json()
        assert payload["error"]["code"] == ErrorCode.DECK_NOT_FOUND.value
