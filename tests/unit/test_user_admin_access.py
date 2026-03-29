from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from mnemo.api.dependencies import get_current_user_from_token
from mnemo.core.constants import PermissionScope
from mnemo.main import app
from mnemo.models.user import User


@pytest.mark.asyncio
async def test_admin_can_access_other_user(monkeypatch: pytest.MonkeyPatch) -> None:
    # Create a target user to be returned by user_service.get_user_by_id
    target = User(
        id="usr_a1b2c3d4e5f6a7b8",
        email="target@example.com",
        normalized_email="target@example.com",
        email_verified=False,
        display_name="Target User",
        country="US",
        locale="en-US",
        timezone="America/New_York",
        education_level=None,
        preferred_language="en",
        daily_goal_cards=20,
        role="user",
    )
    # Provide required audit fields expected by UserResponse

    target.created_at = datetime.now(UTC)

    # Create a current (admin) user
    admin_user = User(
        id="usr_deadbeefcafebabe",
        email="admin@example.com",
        normalized_email="admin@example.com",
        email_verified=False,
        display_name="Admin",
        country="US",
        locale="en-US",
        timezone="America/New_York",
        education_level=None,
        preferred_language="en",
        daily_goal_cards=20,
        role="admin",
    )
    # Attach token_scopes indicating admin
    admin_user.token_scopes = [PermissionScope.ADMIN.value]
    admin_user.created_at = datetime.now(UTC)

    # Override dependencies
    app.dependency_overrides.clear()
    try:
        app.dependency_overrides[get_current_user_from_token] = lambda: admin_user

        async def fake_get_user_by_id(db, user_id):
            return target

        monkeypatch.setattr("mnemo.services.user.get_user_by_id", fake_get_user_by_id)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"/v1/users/{target.id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == target.id
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_non_admin_cannot_access_other_user(monkeypatch: pytest.MonkeyPatch) -> None:
    target = User(
        id="usr_b1b2c3d4e5f6a7b8",
        email="target2@example.com",
        normalized_email="target2@example.com",
        email_verified=False,
        display_name="Target 2",
        country="US",
        locale="en-US",
        timezone="America/New_York",
        education_level=None,
        preferred_language="en",
        daily_goal_cards=20,
        role="user",
    )
    # Provide required audit fields expected by UserResponse

    target.created_at = datetime.now(UTC)

    # Non-admin current user
    user = User(
        id="usr_feedfacecafef00d",
        email="normal@example.com",
        normalized_email="normal@example.com",
        email_verified=False,
        display_name="Normal",
        country="US",
        locale="en-US",
        timezone="America/New_York",
        education_level=None,
        preferred_language="en",
        daily_goal_cards=20,
        role="user",
    )
    user.token_scopes = []

    user.created_at = datetime.now(UTC)

    app.dependency_overrides.clear()
    try:
        app.dependency_overrides[get_current_user_from_token] = lambda: user

        def fake_get_user_by_id(db, user_id):
            return target

        monkeypatch.setattr("mnemo.services.user.get_user_by_id", fake_get_user_by_id)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(f"/v1/users/{target.id}")

            assert resp.status_code == 403
            assert resp.json()["error"]["code"] == "INSUFFICIENT_SCOPE"
    finally:
        app.dependency_overrides.clear()


# Added user.created_at and wrapped test in try/finally to ensure cleanup.
