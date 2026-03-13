"""
Unit tests for src/mnemo/services/api_key.py (pure functions only).
hash_api_key, verify_api_key, get_key_scopes, has_scope — no DB needed.
"""

import json
from unittest.mock import MagicMock

from mnemo.core.constants import PermissionScope
from mnemo.models.api_key import APIKey
from mnemo.services.api_key import (
    get_key_scopes,
    has_scope,
    hash_api_key,
    verify_api_key,
)

# ── hash_api_key ───────────────────────────────────────────────────────────────


def test_hash_api_key_returns_string():
    """hash_api_key must return a non-empty hex string."""
    result = hash_api_key("somekey")
    assert isinstance(result, str)
    assert len(result) == 64  # SHA-256 hex digest is always 64 chars


def test_hash_api_key_is_deterministic():
    """Same key must produce the same hash (HMAC is deterministic)."""
    assert hash_api_key("mykey") == hash_api_key("mykey")


def test_hash_api_key_different_keys_differ():
    """Different keys must produce different hashes."""
    assert hash_api_key("key_a") != hash_api_key("key_b")


def test_hash_api_key_handles_long_key():
    """Keys longer than 72 bytes must not raise (bcrypt regression guard)."""
    long_key = "mnm_live_" + "x" * 64  # 73 bytes — previously broke bcrypt
    result = hash_api_key(long_key)
    assert isinstance(result, str) and len(result) == 64


# ── verify_api_key ─────────────────────────────────────────────────────────────


def test_verify_api_key_correct():
    stored = hash_api_key("mykey")
    assert verify_api_key("mykey", stored) is True


def test_verify_api_key_wrong_key():
    stored = hash_api_key("mykey")
    assert verify_api_key("wrongkey", stored) is False


def test_verify_api_key_bool_return_type():
    stored = hash_api_key("somekey")
    result = verify_api_key("somekey", stored)
    assert isinstance(result, bool)


# ── get_key_scopes ─────────────────────────────────────────────────────────────


def _make_api_key(scopes_json: str) -> MagicMock:
    """Return a mock APIKey with a given scopes JSON string."""
    mock_key = MagicMock(spec=APIKey)
    mock_key.scopes = scopes_json
    return mock_key


def test_get_key_scopes_valid_json():
    scopes = ["decks:read", "sessions:run"]
    mock_key = _make_api_key(json.dumps(scopes))
    result = get_key_scopes(mock_key)
    assert result == scopes


def test_get_key_scopes_invalid_json():
    mock_key = _make_api_key("not-valid-json")
    result = get_key_scopes(mock_key)
    assert result == []


def test_get_key_scopes_none_scopes():
    mock_key = _make_api_key(None)  # type: ignore[arg-type]
    result = get_key_scopes(mock_key)
    assert result == []


def test_get_key_scopes_empty_list():
    mock_key = _make_api_key(json.dumps([]))
    result = get_key_scopes(mock_key)
    assert result == []


# ── has_scope ──────────────────────────────────────────────────────────────────


def test_has_scope_matching():
    mock_key = _make_api_key(json.dumps(["decks:read", "decks:write"]))
    assert has_scope(mock_key, PermissionScope.DECKS_READ) is True


def test_has_scope_not_matching():
    mock_key = _make_api_key(json.dumps(["decks:read"]))
    assert has_scope(mock_key, PermissionScope.DECKS_WRITE) is False


def test_has_scope_admin_grants_all():
    mock_key = _make_api_key(json.dumps([PermissionScope.ADMIN.value]))
    assert has_scope(mock_key, PermissionScope.DECKS_WRITE) is True
    assert has_scope(mock_key, PermissionScope.SESSIONS_RUN) is True
    assert has_scope(mock_key, PermissionScope.IMPORT_WRITE) is True


def test_has_scope_empty_scopes():
    mock_key = _make_api_key(json.dumps([]))
    assert has_scope(mock_key, PermissionScope.DECKS_READ) is False
