"""
Unit tests for src/mnemo/services/auth.py.
All JWT operations are tested with mocked jose calls — no real DB needed.
"""

from datetime import timedelta
from unittest.mock import patch

from jose import JWTError

from mnemo.core.constants import PermissionScope
from mnemo.services.auth import (
    create_access_token,
    decode_access_token,
    get_token_scopes,
    get_token_user_id,
    is_token_expired,
    token_has_scope,
)

# ── create_access_token ────────────────────────────────────────────────────────


def test_create_access_token_returns_string():
    token = create_access_token("usr_123", ["decks:read"])
    assert isinstance(token, str)
    assert len(token) > 0


def test_create_access_token_custom_expiry():
    token = create_access_token("usr_abc", ["admin"], expires_delta=timedelta(minutes=5))
    assert isinstance(token, str)


def test_create_access_token_empty_scopes():
    token = create_access_token("usr_xyz", [])
    assert isinstance(token, str)


# ── decode_access_token ────────────────────────────────────────────────────────


def test_decode_access_token_valid():
    token = create_access_token("usr_111", ["decks:read"])
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "usr_111"
    assert "decks:read" in payload["scopes"]


def test_decode_access_token_invalid_token():
    result = decode_access_token("this.is.not.a.valid.jwt")
    assert result is None


def test_decode_access_token_jwt_error():
    with patch("mnemo.services.auth.jwt.decode", side_effect=JWTError("bad token")):
        result = decode_access_token("some.fake.token")
    assert result is None


# ── get_token_user_id ──────────────────────────────────────────────────────────


def test_get_token_user_id_valid():
    token = create_access_token("usr_999", ["decks:read"])
    user_id = get_token_user_id(token)
    assert user_id == "usr_999"


def test_get_token_user_id_invalid_token():
    result = get_token_user_id("garbage")
    assert result is None


def test_get_token_user_id_missing_sub():
    with patch("mnemo.services.auth.decode_access_token", return_value={"scopes": []}):
        result = get_token_user_id("any.token.here")
    assert result is None


# ── get_token_scopes ───────────────────────────────────────────────────────────


def test_get_token_scopes_valid():
    token = create_access_token("usr_200", ["decks:read", "sessions:run"])
    scopes = get_token_scopes(token)
    assert "decks:read" in scopes
    assert "sessions:run" in scopes


def test_get_token_scopes_invalid_token():
    scopes = get_token_scopes("not.a.token")
    assert scopes == []


def test_get_token_scopes_missing_scopes_key():
    with patch("mnemo.services.auth.decode_access_token", return_value={"sub": "usr_1"}):
        scopes = get_token_scopes("any.token.here")
    assert scopes == []


# ── token_has_scope ────────────────────────────────────────────────────────────


def test_token_has_scope_matching_scope():
    token = create_access_token("usr_300", [PermissionScope.DECKS_READ.value])
    assert token_has_scope(token, PermissionScope.DECKS_READ) is True


def test_token_has_scope_missing_scope():
    token = create_access_token("usr_300", [PermissionScope.DECKS_READ.value])
    assert token_has_scope(token, PermissionScope.DECKS_WRITE) is False


def test_token_has_scope_admin_grants_all():
    token = create_access_token("usr_300", [PermissionScope.ADMIN.value])
    assert token_has_scope(token, PermissionScope.DECKS_WRITE) is True
    assert token_has_scope(token, PermissionScope.SESSIONS_RUN) is True


def test_token_has_scope_invalid_token():
    assert token_has_scope("garbage.token", PermissionScope.DECKS_READ) is False


# ── is_token_expired ───────────────────────────────────────────────────────────


def test_is_token_expired_fresh_token():
    token = create_access_token("usr_400", ["decks:read"])
    assert is_token_expired(token) is False


def test_is_token_expired_invalid_token():
    assert is_token_expired("not.a.valid.token") is True


def test_is_token_expired_expired_token():
    token = create_access_token("usr_400", ["decks:read"], expires_delta=timedelta(seconds=-1))
    # Token is expired — decode returns None because jose raises JWTError for expired tokens
    assert is_token_expired(token) is True


def test_is_token_expired_missing_exp():
    with patch(
        "mnemo.services.auth.decode_access_token",
        return_value={"sub": "usr_1", "scopes": []},
    ):
        assert is_token_expired("any.token") is True
