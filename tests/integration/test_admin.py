"""
Integration tests for admin user-management endpoints:
  POST   /v1/admin/provision
  GET    /v1/admin/users
  DELETE /v1/admin/users/{user_id}
  GET    /v1/admin/users/{user_id}/decks

…and consent endpoints:
  POST   /v1/user/grant-admin-access
  DELETE /v1/user/grant-admin-access
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.core.constants import PermissionScope
from mnemo.main import app
from mnemo.models.user import User
from mnemo.schemas.user import UserCreate
from mnemo.services.api_key import create_api_key
from mnemo.services.user import create_user

# ── Shared fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
async def admin_user_with_key(db_session: AsyncSession) -> tuple[User, str]:
    """Admin user (created via create_user, API key with ADMIN scope)."""
    user_data = UserCreate(
        display_name="AdminActor",
        country="CM",
        timezone="Africa/Douala",
        locale="fr-CM",
        preferred_language="fr",
        daily_goal_cards=10,
    )
    user = await create_user(db_session, user_data)
    # Give the user an admin role so the JWT scopes match
    user.role = "admin"
    _, plain_key = await create_api_key(
        db=db_session,
        user_id=user.id,
        name="Admin Key",
        is_live=True,
        scopes=[PermissionScope.ADMIN],
    )
    await db_session.commit()
    return user, plain_key


@pytest.fixture
async def regular_user_with_key(db_session: AsyncSession) -> tuple[User, str]:
    """Regular (non-admin) user."""
    user_data = UserCreate(
        display_name="RegularJoe",
        country="GB",
        locale="en-GB",
        preferred_language="en",
        daily_goal_cards=5,
    )
    user = await create_user(db_session, user_data)
    _, plain_key = await create_api_key(
        db=db_session,
        user_id=user.id,
        name="User Key",
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


async def _get_jwt(client: AsyncClient, user_id: str, api_key: str) -> str:
    """Exchange an API key for a JWT and return the raw token string."""
    resp = await client.post("/v1/auth/token", json={"user_id": user_id, "api_key": api_key})
    assert resp.status_code == 200, f"auth/token failed: {resp.text}"
    return str(resp.json()["access_token"])


# ── POST /v1/admin/provision ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_provision_user(
    db_session: AsyncSession, admin_user_with_key: tuple[User, str]
) -> None:
    """Admin can provision a new regular user."""
    admin, admin_key = admin_user_with_key
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        jwt = await _get_jwt(client, admin.id, admin_key)

        resp = await client.post(
            "/v1/admin/provision",
            json={"display_name": "NewUser", "country": "CM"},
            headers={"Authorization": f"Bearer {jwt}"},
        )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["role"] == "user"
    assert data["display_name"] == "NewUser"
    assert data["user_id"].startswith("usr_")
    assert data["api_key"].startswith("mnm_")


@pytest.mark.asyncio
async def test_admin_provision_admin_role(
    db_session: AsyncSession, admin_user_with_key: tuple[User, str]
) -> None:
    """Admin provisioning with role='admin' results in an admin-role account."""
    admin, admin_key = admin_user_with_key
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        jwt = await _get_jwt(client, admin.id, admin_key)

        resp = await client.post(
            "/v1/admin/provision",
            json={"display_name": "SuperAdmin", "country": "CM", "role": "admin"},
            headers={"Authorization": f"Bearer {jwt}"},
        )
    assert resp.status_code == 201, resp.text
    assert resp.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_non_admin_provision_returns_403(
    db_session: AsyncSession, regular_user_with_key: tuple[User, str]
) -> None:
    """A non-admin JWT receives 403 when calling POST /v1/admin/provision."""
    user, key = regular_user_with_key
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        jwt = await _get_jwt(client, user.id, key)

        resp = await client.post(
            "/v1/admin/provision",
            json={"country": "GB"},
            headers={"Authorization": f"Bearer {jwt}"},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_provision_duplicate_name_returns_409(
    db_session: AsyncSession, admin_user_with_key: tuple[User, str]
) -> None:
    """Provisioning a duplicate display_name via admin endpoint returns 409."""
    admin, admin_key = admin_user_with_key
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        jwt = await _get_jwt(client, admin.id, admin_key)

        r1 = await client.post(
            "/v1/admin/provision",
            json={"display_name": "Dupe", "country": "CM"},
            headers={"Authorization": f"Bearer {jwt}"},
        )
        assert r1.status_code == 201

        r2 = await client.post(
            "/v1/admin/provision",
            json={"display_name": "Dupe", "country": "CM"},
            headers={"Authorization": f"Bearer {jwt}"},
        )
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "DISPLAY_NAME_CONFLICT"


# ── GET /v1/admin/users ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_list_users(
    db_session: AsyncSession, admin_user_with_key: tuple[User, str]
) -> None:
    """GET /v1/admin/users returns a paginated user list with expected fields."""
    admin, admin_key = admin_user_with_key
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        jwt = await _get_jwt(client, admin.id, admin_key)

        resp = await client.get(
            "/v1/admin/users",
            headers={"Authorization": f"Bearer {jwt}"},
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "users" in data
    assert "total" in data
    assert "page" in data
    assert "per_page" in data
    # At least the admin user itself should be listed
    assert data["total"] >= 1
    user_ids = [u["user_id"] for u in data["users"]]
    assert admin.id in user_ids

    # Verify shape of a user item
    first = data["users"][0]
    assert "deck_count" in first
    assert "has_granted_admin_access" in first
    assert "role" in first


@pytest.mark.asyncio
async def test_admin_list_users_search(
    db_session: AsyncSession, admin_user_with_key: tuple[User, str]
) -> None:
    """?search=partial_name filters the list to matching users."""
    admin, admin_key = admin_user_with_key
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        jwt = await _get_jwt(client, admin.id, admin_key)

        # Provision an extra user with a distinctive name
        await client.post(
            "/v1/admin/provision",
            json={"display_name": "UniqueSearchTarget", "country": "CM"},
            headers={"Authorization": f"Bearer {jwt}"},
        )

        resp = await client.get(
            "/v1/admin/users?search=UniqueSearch",
            headers={"Authorization": f"Bearer {jwt}"},
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 1
    assert data["users"][0]["display_name"] == "UniqueSearchTarget"


@pytest.mark.asyncio
async def test_admin_list_users_pagination(
    db_session: AsyncSession, admin_user_with_key: tuple[User, str]
) -> None:
    """Pagination params (page, per_page) are respected."""
    admin, admin_key = admin_user_with_key
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        jwt = await _get_jwt(client, admin.id, admin_key)

        # Create two more users
        for name in ("PaginationA", "PaginationB"):
            await client.post(
                "/v1/admin/provision",
                json={"display_name": name, "country": "CM"},
                headers={"Authorization": f"Bearer {jwt}"},
            )

        # Ask for 1 per page
        resp = await client.get(
            "/v1/admin/users?page=1&per_page=1",
            headers={"Authorization": f"Bearer {jwt}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["per_page"] == 1
    assert len(data["users"]) == 1
    assert data["total"] >= 3


# ── DELETE /v1/admin/users/{user_id} ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_delete_user(
    db_session: AsyncSession, admin_user_with_key: tuple[User, str]
) -> None:
    """Admin can delete another user; returns 204."""
    admin, admin_key = admin_user_with_key
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        jwt = await _get_jwt(client, admin.id, admin_key)

        # Provision a target user
        prov = await client.post(
            "/v1/admin/provision",
            json={"display_name": "ToDelete", "country": "CM"},
            headers={"Authorization": f"Bearer {jwt}"},
        )
        assert prov.status_code == 201
        target_id = prov.json()["user_id"]

        del_resp = await client.delete(
            f"/v1/admin/users/{target_id}",
            headers={"Authorization": f"Bearer {jwt}"},
        )
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_admin_delete_user_removes_from_list(
    db_session: AsyncSession, admin_user_with_key: tuple[User, str]
) -> None:
    """After deletion the user no longer appears in GET /v1/admin/users."""
    admin, admin_key = admin_user_with_key
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        jwt = await _get_jwt(client, admin.id, admin_key)

        prov = await client.post(
            "/v1/admin/provision",
            json={"display_name": "GoneUser", "country": "CM"},
            headers={"Authorization": f"Bearer {jwt}"},
        )
        target_id = prov.json()["user_id"]

        await client.delete(
            f"/v1/admin/users/{target_id}",
            headers={"Authorization": f"Bearer {jwt}"},
        )

        list_resp = await client.get(
            "/v1/admin/users",
            headers={"Authorization": f"Bearer {jwt}"},
        )
    ids = [u["user_id"] for u in list_resp.json()["users"]]
    assert target_id not in ids


@pytest.mark.asyncio
async def test_admin_delete_self_returns_400(
    db_session: AsyncSession, admin_user_with_key: tuple[User, str]
) -> None:
    """Admin cannot delete their own account; returns 400."""
    admin, admin_key = admin_user_with_key
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        jwt = await _get_jwt(client, admin.id, admin_key)

        resp = await client.delete(
            f"/v1/admin/users/{admin.id}",
            headers={"Authorization": f"Bearer {jwt}"},
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_admin_delete_nonexistent_user_returns_404(
    db_session: AsyncSession, admin_user_with_key: tuple[User, str]
) -> None:
    """Deleting a user that doesn't exist returns 404."""
    admin, admin_key = admin_user_with_key
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        jwt = await _get_jwt(client, admin.id, admin_key)

        resp = await client.delete(
            "/v1/admin/users/usr_0000000000000000",
            headers={"Authorization": f"Bearer {jwt}"},
        )
    assert resp.status_code == 404


# ── GET /v1/admin/users/{user_id}/decks ──────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_get_user_decks_403_when_not_granted(
    db_session: AsyncSession, admin_user_with_key: tuple[User, str]
) -> None:
    """Returns 403 with ADMIN_ACCESS_NOT_GRANTED when user hasn't consented."""
    admin, admin_key = admin_user_with_key
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin_jwt = await _get_jwt(client, admin.id, admin_key)

        # Provision a target user (admin_access_granted defaults to False)
        prov = await client.post(
            "/v1/admin/provision",
            json={"display_name": "NoConsent", "country": "CM"},
            headers={"Authorization": f"Bearer {admin_jwt}"},
        )
        target_id = prov.json()["user_id"]

        resp = await client.get(
            f"/v1/admin/users/{target_id}/decks",
            headers={"Authorization": f"Bearer {admin_jwt}"},
        )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "ADMIN_ACCESS_NOT_GRANTED"


@pytest.mark.asyncio
async def test_admin_get_user_decks_200_after_grant(
    db_session: AsyncSession, admin_user_with_key: tuple[User, str]
) -> None:
    """After user grants admin access, GET /v1/admin/users/{id}/decks returns 200."""
    admin, admin_key = admin_user_with_key
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin_jwt = await _get_jwt(client, admin.id, admin_key)

        # Provision the target user with a password so they can log in
        prov = await client.post(
            "/v1/admin/provision",
            json={"display_name": "ConsentUser", "country": "CM", "password": "password99"},
            headers={"Authorization": f"Bearer {admin_jwt}"},
        )
        assert prov.status_code == 201
        target_id = prov.json()["user_id"]
        target_api_key = prov.json()["api_key"]

        # Target user gets their JWT
        target_jwt = await _get_jwt(client, target_id, target_api_key)

        # Target user grants admin access
        grant_resp = await client.post(
            "/v1/user/grant-admin-access",
            headers={"Authorization": f"Bearer {target_jwt}"},
        )
        assert grant_resp.status_code == 200
        assert grant_resp.json()["admin_access_granted"] is True

        # Admin now fetches target user's decks → 200
        deck_resp = await client.get(
            f"/v1/admin/users/{target_id}/decks",
            headers={"Authorization": f"Bearer {admin_jwt}"},
        )
    assert deck_resp.status_code == 200, deck_resp.text
    data = deck_resp.json()
    assert "data" in data


@pytest.mark.asyncio
async def test_admin_get_user_decks_404_for_unknown_user(
    db_session: AsyncSession, admin_user_with_key: tuple[User, str]
) -> None:
    """Returns 404 when the target user does not exist."""
    admin, admin_key = admin_user_with_key
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        jwt = await _get_jwt(client, admin.id, admin_key)

        resp = await client.get(
            "/v1/admin/users/usr_0000000000000000/decks",
            headers={"Authorization": f"Bearer {jwt}"},
        )
    assert resp.status_code == 404


# ── /v1/user/grant-admin-access toggle ───────────────────────────────────────


@pytest.mark.asyncio
async def test_grant_admin_access_toggle(db_session: AsyncSession) -> None:
    """POST grants, DELETE revokes; response body reflects the current state."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Self-register a user with a password
        prov = await client.post(
            "/v1/user/provision",
            json={"display_name": "ToggleUser", "country": "CM", "password": "pass1234"},
        )
        assert prov.status_code == 201
        user_id = prov.json()["user_id"]
        api_key = prov.json()["api_key"]

        jwt = await _get_jwt(client, user_id, api_key)
        auth = {"Authorization": f"Bearer {jwt}"}

        # Default: not granted
        grant = await client.post("/v1/user/grant-admin-access", headers=auth)
        assert grant.status_code == 200
        assert grant.json()["admin_access_granted"] is True
        assert grant.json()["granted_at"] is not None

        revoke = await client.delete("/v1/user/grant-admin-access", headers=auth)
        assert revoke.status_code == 200
        assert revoke.json()["admin_access_granted"] is False
        assert revoke.json()["granted_at"] is None


@pytest.mark.asyncio
async def test_grant_admin_access_requires_auth(db_session: AsyncSession) -> None:
    """POST /v1/user/grant-admin-access without a JWT returns 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/v1/user/grant-admin-access")
    assert resp.status_code == 401
