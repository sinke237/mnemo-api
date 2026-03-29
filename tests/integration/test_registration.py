"""
Integration tests for user self-registration (POST /v1/user/provision)
and password login (POST /v1/auth/login).
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.main import app
from mnemo.services.user import get_user_by_id

# ── POST /v1/user/provision ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_provision_user_happy_path(db_session: AsyncSession) -> None:
    """Provisioning a new regular user returns user_id, api_key, display_name, role."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/v1/user/provision",
            json={
                "display_name": "Alice",
                "country": "CM",
                "password": "securePass1",
            },
        )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["role"] == "user"
    assert data["display_name"] == "Alice"
    assert data["user_id"].startswith("usr_")
    assert data["api_key"].startswith("mnm_")
    # Verify the API key is not the hashed version (plaintext has exactly 3 segments)
    assert len(data["api_key"].split("_")) == 3


@pytest.mark.asyncio
async def test_provision_user_no_password(db_session: AsyncSession) -> None:
    """Passwordless provision still succeeds; account is created without password_hash."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/v1/user/provision",
            json={"country": "GB"},
        )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["role"] == "user"
    assert data["display_name"] is None

    # Confirm password_hash is not exposed in the response
    assert "password_hash" not in data
    assert "password" not in data


@pytest.mark.asyncio
async def test_provision_user_password_hashing(db_session: AsyncSession) -> None:
    """The stored password_hash must NOT equal the plain password."""
    plain = "MySecret99"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/v1/user/provision",
            json={
                "display_name": "Bob",
                "country": "US",
                "timezone": "America/New_York",
                "password": plain,
            },
        )
    assert resp.status_code == 201, resp.text
    user_id = resp.json()["user_id"]

    # Check DB record directly
    user = await get_user_by_id(db_session, user_id)
    assert user is not None
    assert user.password_hash is not None
    assert user.password_hash != plain


@pytest.mark.asyncio
async def test_provision_user_duplicate_display_name(db_session: AsyncSession) -> None:
    """Second registration with the same display_name returns 409."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r1 = await client.post(
            "/v1/user/provision",
            json={"display_name": "Charlie", "country": "NG"},
        )
        assert r1.status_code == 201, r1.text

        r2 = await client.post(
            "/v1/user/provision",
            json={"display_name": "Charlie", "country": "CM"},
        )
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "DISPLAY_NAME_CONFLICT"


@pytest.mark.asyncio
async def test_provision_user_invalid_country(db_session: AsyncSession) -> None:
    """Invalid country code returns 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/v1/user/provision",
            json={"country": "XX"},
        )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_COUNTRY_CODE"


@pytest.mark.asyncio
async def test_provision_user_missing_timezone_multi_tz_country(
    db_session: AsyncSession,
) -> None:
    """US has multiple timezones — omitting timezone returns 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/v1/user/provision",
            json={"country": "US"},
        )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_TIMEZONE"


@pytest.mark.asyncio
async def test_provision_user_password_too_short(db_session: AsyncSession) -> None:
    """Password shorter than 8 characters fails Pydantic validation (422)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/v1/user/provision",
            json={"country": "CM", "password": "short"},
        )
    assert resp.status_code == 422


# ── POST /v1/auth/login ───────────────────────────────────────────────────────


@pytest.fixture
async def user_with_password(db_session: AsyncSession) -> tuple[str, str]:
    """Create a user with a known password via the provision endpoint.

    Returns (display_name, password).
    """
    display_name = "LoginUser"
    plain_password = "TestPass99"  # noqa: S105
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/v1/user/provision",
            json={"display_name": display_name, "country": "CM", "password": plain_password},
        )
    assert resp.status_code == 201
    return display_name, plain_password


@pytest.mark.asyncio
async def test_login_correct_credentials(
    db_session: AsyncSession, user_with_password: tuple[str, str]
) -> None:
    """Correct credentials return a valid JWT (same shape as /v1/auth/token)."""
    display_name, password = user_with_password
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/v1/auth/login",
            json={"display_name": display_name, "password": password},
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "Bearer"  # noqa: S105
    assert data["expires_in"] > 0


@pytest.mark.asyncio
async def test_login_wrong_password(
    db_session: AsyncSession, user_with_password: tuple[str, str]
) -> None:
    """Wrong password returns 401 with INVALID_CREDENTIALS (no user enumeration)."""
    display_name, _ = user_with_password
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/v1/auth/login",
            json={"display_name": display_name, "password": "wrongpassword"},
        )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_unknown_display_name(db_session: AsyncSession) -> None:
    """Unknown display_name returns the same 401 as wrong password (no enumeration)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/v1/auth/login",
            json={"display_name": "nobody_here", "password": "doesntmatter"},
        )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_passwordless_account_returns_401(db_session: AsyncSession) -> None:
    """A passwordless account cannot use /v1/auth/login (must use API key instead)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/v1/user/provision",
            json={"display_name": "NoPass", "country": "CM"},
        )
        resp = await client.post(
            "/v1/auth/login",
            json={"display_name": "NoPass", "password": "anypassword"},
        )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"
