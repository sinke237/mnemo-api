"""
Integration tests for full authentication flow.
Tests the complete user journey: create user → get API key → get JWT → access profile.
"""

from datetime import datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.core.constants import PermissionScope
from mnemo.main import app
from mnemo.models.user import User
from mnemo.schemas.user import UserProvisionRequest as UserCreate
from mnemo.services.api_key import create_api_key
from mnemo.services.auth import create_access_token
from mnemo.services.user import create_user
from mnemo.utils.local_time import to_local_time


def _parse_iso_datetime(value: str) -> datetime:
    """Parse ISO 8601 with optional 'Z' suffix."""
    if value.endswith("Z"):
        value = value.replace("Z", "+00:00")
    return datetime.fromisoformat(value)


@pytest.fixture
async def admin_user_with_key(db_session: AsyncSession) -> tuple[User, str]:
    """Create an admin user with an API key for testing."""
    # Create user
    user_data = UserCreate(
        email="test-admin@example.com",
        password="securePass123",
        display_name="Test Admin",
        country="CM",
        timezone="Africa/Douala",
        locale="fr-CM",
        preferred_language="fr",
        daily_goal_cards=20,
    )
    user = await create_user(db_session, user_data)

    # Create API key with admin scope
    _, plain_key = await create_api_key(
        db=db_session,
        user_id=user.id,
        name="Test Admin Key",
        is_live=True,
        scopes=[PermissionScope.ADMIN],
    )

    await db_session.commit()

    return user, plain_key


@pytest.fixture
async def regular_user_with_key(db_session: AsyncSession) -> tuple[User, str]:
    """Create a regular user with standard scopes for testing."""
    # Create user
    user_data = UserCreate(
        email="regular-user@example.com",
        password="securePass123",
        display_name="Regular User",
        country="US",
        timezone="America/New_York",
        locale="en-US",
        preferred_language="en",
        daily_goal_cards=25,
    )
    user = await create_user(db_session, user_data)

    # Create API key with standard scopes (no admin)
    _, plain_key = await create_api_key(
        db=db_session,
        user_id=user.id,
        name="Test User Key",
        is_live=False,
        scopes=[
            PermissionScope.DECKS_READ,
            PermissionScope.DECKS_WRITE,
            PermissionScope.SESSIONS_RUN,
            PermissionScope.PROGRESS_READ,
        ],
    )

    await db_session.commit()

    return user, plain_key


@pytest.mark.asyncio
async def test_full_auth_flow_admin_user(admin_user_with_key: tuple[User, str]) -> None:
    """
    Test complete auth flow for admin user:
    1. Get JWT token using API key
    2. Access own profile with JWT
    3. Update profile with JWT
    """
    user, api_key = admin_user_with_key

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Step 1: Get JWT token
        token_response = await client.post(
            "/v1/auth/token",
            json={"user_id": user.id, "api_key": api_key},
        )
        assert token_response.status_code == 200
        token_data = token_response.json()
        assert "access_token" in token_data
        assert token_data["token_type"] == "Bearer"  # noqa: S105
        assert token_data["expires_in"] == 3600

        jwt_token = token_data["access_token"]

        # Step 2: Access own profile
        profile_response = await client.get(
            f"/v1/users/{user.id}",
            headers={"Authorization": f"Bearer {jwt_token}"},
        )
        assert profile_response.status_code == 200
        profile_data = profile_response.json()
        assert profile_data["id"] == user.id
        assert profile_data["display_name"] == "Test Admin"
        assert profile_data["country"] == "CM"
        assert profile_data["timezone"] == "Africa/Douala"
        assert "local_time" in profile_data
        assert "created_at_local" in profile_data
        created_at = _parse_iso_datetime(profile_data["created_at"])
        expected_local_time = to_local_time(created_at, profile_data["timezone"])
        assert profile_data["local_time"] == expected_local_time
        assert profile_data["created_at_local"] == expected_local_time
        assert profile_data["created_at_local"] == profile_data["local_time"]

        # Step 3: Update profile
        update_response = await client.patch(
            f"/v1/users/{user.id}",
            headers={"Authorization": f"Bearer {jwt_token}"},
            json={"daily_goal_cards": 30, "display_name": "Updated Admin"},
        )
        assert update_response.status_code == 200
        updated_data = update_response.json()
        assert updated_data["daily_goal_cards"] == 30
        assert updated_data["display_name"] == "Updated Admin"


@pytest.mark.asyncio
async def test_admin_can_access_other_users(
    admin_user_with_key: tuple[User, str],
    regular_user_with_key: tuple[User, str],
) -> None:
    """Test that admin users can access other users' profiles."""
    admin_user, admin_key = admin_user_with_key
    regular_user, _ = regular_user_with_key

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Get admin JWT token
        token_response = await client.post(
            "/v1/auth/token",
            json={"user_id": admin_user.id, "api_key": admin_key},
        )
        assert token_response.status_code == 200
        admin_token = token_response.json()["access_token"]

        # Admin accesses regular user's profile
        profile_response = await client.get(
            f"/v1/users/{regular_user.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert profile_response.status_code == 200
        profile_data = profile_response.json()
        assert profile_data["id"] == regular_user.id
        assert profile_data["display_name"] == "Regular User"


@pytest.mark.asyncio
async def test_regular_user_cannot_access_other_users(
    admin_user_with_key: tuple[User, str],
    regular_user_with_key: tuple[User, str],
) -> None:
    """Test that non-admin users cannot access other users' profiles."""
    admin_user, _ = admin_user_with_key
    regular_user, regular_key = regular_user_with_key

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Get regular user JWT token
        token_response = await client.post(
            "/v1/auth/token",
            json={"user_id": regular_user.id, "api_key": regular_key},
        )
        assert token_response.status_code == 200
        regular_token = token_response.json()["access_token"]

        # Regular user tries to access admin's profile
        profile_response = await client.get(
            f"/v1/users/{admin_user.id}",
            headers={"Authorization": f"Bearer {regular_token}"},
        )
        assert profile_response.status_code == 403
        error_data = profile_response.json()
        assert error_data["error"]["code"] == "INSUFFICIENT_SCOPE"


@pytest.mark.asyncio
async def test_invalid_api_key_rejected() -> None:
    """Test that invalid API keys are rejected."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/v1/auth/token",
            json={
                # Valid format, but non-existent user and key
                "user_id": "usr_0000000000000000",
                "api_key": "mnm_test_" + "0" * 64,  # Valid format, but not in DB
            },
        )
        assert response.status_code == 401
        error_data = response.json()
        assert error_data["error"]["code"] == "INVALID_API_KEY"


@pytest.mark.asyncio
async def test_invalid_jwt_rejected(regular_user_with_key: tuple[User, str]) -> None:
    """Test that malformed JWT tokens are rejected."""
    user, _ = regular_user_with_key

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            f"/v1/users/{user.id}",
            headers={"Authorization": "Bearer invalid.jwt.token"},
        )
        assert response.status_code == 401
        error_data = response.json()
        assert error_data["error"]["code"] == "INVALID_TOKEN"


@pytest.mark.asyncio
async def test_expired_jwt_rejected(regular_user_with_key: tuple[User, str]) -> None:
    """Test that expired JWT tokens are rejected."""
    user, _ = regular_user_with_key
    expired_token = create_access_token(
        user.id,
        [PermissionScope.DECKS_READ.value],
        expires_delta=timedelta(seconds=-1),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            f"/v1/users/{user.id}",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert response.status_code == 401
        error_data = response.json()
        assert error_data["error"]["code"] == "TOKEN_EXPIRED"


@pytest.mark.asyncio
async def test_missing_authorization_header(regular_user_with_key: tuple[User, str]) -> None:
    """Test that requests without Authorization header are rejected."""
    user, _ = regular_user_with_key

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/v1/users/{user.id}")
        assert response.status_code == 401
        error_data = response.json()
        assert error_data["error"]["code"] == "INVALID_TOKEN"


@pytest.mark.asyncio
async def test_create_user_requires_admin_scope(
    regular_user_with_key: tuple[User, str],
) -> None:
    """Test that creating users requires admin scope."""
    _, regular_key = regular_user_with_key

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/v1/users",
            headers={"X-API-Key": regular_key},
            json={
                "display_name": "New User",
                "country": "GB",
                "preferred_language": "en",
                "daily_goal_cards": 20,
            },
        )
        assert response.status_code == 403
        error_data = response.json()
        assert error_data["error"]["code"] == "INSUFFICIENT_SCOPE"


@pytest.mark.asyncio
async def test_multi_timezone_country_requires_timezone(
    admin_user_with_key: tuple[User, str],
) -> None:
    """Test that multi-timezone countries require explicit timezone selection."""
    _, admin_key = admin_user_with_key

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Try creating US user without timezone
        response = await client.post(
            "/v1/users",
            headers={"X-API-Key": admin_key},
            json={
                "email": "ususer@example.com",
                "password": "securePass123",
                "display_name": "US User",
                "country": "US",
                "preferred_language": "en",
                "daily_goal_cards": 20,
            },
        )
        assert response.status_code == 400
        error_data = response.json()
        assert error_data["error"]["code"] == "INVALID_TIMEZONE"


@pytest.mark.asyncio
async def test_update_profile_own_user_only(
    regular_user_with_key: tuple[User, str],
    admin_user_with_key: tuple[User, str],
) -> None:
    """Test that users can only update their own profile."""
    user, user_key = regular_user_with_key
    other_user, _ = admin_user_with_key

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Get JWT token
        token_response = await client.post(
            "/v1/auth/token",
            json={"user_id": user.id, "api_key": user_key},
        )
        assert token_response.status_code == 200, f"Token request failed: {token_response.text}"
        token_data = token_response.json()
        assert "access_token" in token_data
        jwt_token = token_data["access_token"]

        # Try to update another user's profile (real user ID)
        response = await client.patch(
            f"/v1/users/{other_user.id}",
            headers={"Authorization": f"Bearer {jwt_token}"},
            json={"daily_goal_cards": 50},
        )
        assert response.status_code == 403
        error_data = response.json()
        assert error_data["error"]["code"] == "INSUFFICIENT_SCOPE"
