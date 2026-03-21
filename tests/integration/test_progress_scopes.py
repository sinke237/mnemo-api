import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.core.constants import PermissionScope
from mnemo.main import app
from mnemo.schemas.user import UserCreate
from mnemo.services.api_key import create_api_key
from mnemo.services.deck import create_deck
from mnemo.services.user import create_user

# `db_session` fixture is provided by tests.test_fixtures.py


@pytest.mark.asyncio
async def test_progress_endpoints_require_scope(db_session: AsyncSession) -> None:
    # Create a user
    user_data = UserCreate(
        display_name="Scope Test",
        country="US",
        timezone="America/New_York",
        locale="en-US",
        preferred_language="en",
        daily_goal_cards=10,
    )
    user = await create_user(db_session, user_data)

    # Create a deck owned by the user (needed for deck-progress scope check)
    deck = await create_deck(
        db=db_session,
        user_id=user.id,
        name="Scope Test Deck",
        description=None,
        tags=[],
    )

    # Create API key WITHOUT PROGRESS_READ
    _, key_no_scope = await create_api_key(
        db=db_session,
        user_id=user.id,
        name="no-progress-key",
        is_live=False,
        scopes=[PermissionScope.DECKS_READ],
    )

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
        # Get JWT for key without scope
        token_resp = await client.post(
            "/v1/auth/token", json={"user_id": user.id, "api_key": key_no_scope}
        )
        assert token_resp.status_code == 200
        token_no_scope = token_resp.json()["access_token"]

        # Access progress -> should be 403
        resp = await client.get(
            f"/v1/users/{user.id}/progress", headers={"Authorization": f"Bearer {token_no_scope}"}
        )
        assert resp.status_code == 403

        # Access deck progress without scope -> should be 403
        resp_deck_no_scope = await client.get(
            f"/v1/users/{user.id}/progress/{deck.id}",
            headers={"Authorization": f"Bearer {token_no_scope}"},
        )
        assert resp_deck_no_scope.status_code == 403

        # Get JWT for key with scope
        token_resp2 = await client.post(
            "/v1/auth/token", json={"user_id": user.id, "api_key": key_with_scope}
        )
        assert token_resp2.status_code == 200
        token_with_scope = token_resp2.json()["access_token"]

        # Access progress -> should be 200
        resp2 = await client.get(
            f"/v1/users/{user.id}/progress", headers={"Authorization": f"Bearer {token_with_scope}"}
        )
        assert resp2.status_code == 200

        # Access deck progress with scope -> should be 200
        resp_deck_with_scope = await client.get(
            f"/v1/users/{user.id}/progress/{deck.id}",
            headers={"Authorization": f"Bearer {token_with_scope}"},
        )
        assert resp_deck_with_scope.status_code == 200

        # Access streak -> should be 200 with scope
        resp3 = await client.get(
            f"/v1/users/{user.id}/streak", headers={"Authorization": f"Bearer {token_with_scope}"}
        )
        assert resp3.status_code == 200
