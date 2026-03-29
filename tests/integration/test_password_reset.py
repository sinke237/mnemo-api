import secrets

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.main import app
from mnemo.services import password_reset as password_reset_service


@pytest.mark.asyncio
async def test_password_reset_token_lifecycle(db_session: AsyncSession) -> None:
    # Provision a user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/v1/user/provision",
            json={
                "email": "prtlifecycle@example.com",
                "display_name": "PrtUser",
                "country": "CM",
                "password": "Initial1Pass",
            },
        )
    assert resp.status_code == 201, resp.text
    user_id = resp.json()["user_id"]

    # Create token
    token = await password_reset_service.create_token(db_session, user_id)
    assert isinstance(token, str) and token

    # Lookup token by plaintext
    token_row = await password_reset_service.get_token_by_plain(db_session, token)
    assert token_row is not None

    # Consume the token atomically and ensure it is no longer found
    consumed = await password_reset_service.consume_token_by_plain(db_session, token)
    assert consumed is not None
    token_row_after = await password_reset_service.get_token_by_plain(db_session, token)
    assert token_row_after is None


@pytest.mark.asyncio
async def test_reset_endpoint_resets_password(db_session: AsyncSession) -> None:
    # Provision a user
    email = "resetflow@example.com"
    # Ensure generated passwords meet complexity requirements (uppercase,
    # lowercase, digit). Use deterministic suffix to satisfy validators.
    old_password = secrets.token_urlsafe(6) + "Aa1"
    new_password = secrets.token_urlsafe(6) + "Bb1"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/v1/user/provision",
            json={
                "email": email,
                "display_name": "ResetUser",
                "country": "CM",
                "password": old_password,
            },
        )
    assert resp.status_code == 201, resp.text
    user_id = resp.json()["user_id"]

    # Create token directly via service (plaintext returned)
    token = await password_reset_service.create_token(db_session, user_id)
    # Commit the token so the request-scoped DB session in the test server
    # can see it (tests use separate sessions bound to the same connection).
    await db_session.commit()

    # Call reset endpoint with the token
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/v1/user/reset-password",
            json={"token": token, "new_password": new_password},
        )
    assert resp.status_code == 200, resp.text

    # Re-using the same token should fail because tokens are single-use
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp_reuse = await client.post(
            "/v1/user/reset-password",
            json={"token": token, "new_password": new_password},
        )
    assert resp_reuse.status_code != 200, (
        "Reusing a password reset token should fail: " + resp_reuse.text
    )

    # Verify login with new password succeeds
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/v1/auth/login", json={"email": email, "password": new_password})
    assert resp.status_code == 200, resp.text
