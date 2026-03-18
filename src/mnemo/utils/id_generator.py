"""
ID generation utilities.
Generates human-readable prefixed IDs per spec (usr_, dck_, crd_, etc.).
"""

import secrets

from mnemo.core.constants import API_KEY_LIVE_TYPE, API_KEY_PREFIX, API_KEY_TEST_TYPE


def generate_user_id() -> str:
    """Generate a user ID with prefix usr_"""
    return f"usr_{secrets.token_hex(8)}"


def generate_api_key(is_live: bool = False) -> str:
    """
    Generate an API key with appropriate prefix.

    Args:
        is_live: If True, generates a key with the configured live prefix, else the test prefix.

    Returns:
        API key string with prefix
    """
    key_type = API_KEY_LIVE_TYPE if is_live else API_KEY_TEST_TYPE
    prefix = f"{API_KEY_PREFIX}_{key_type}_"
    # Generate 32 random bytes for the key portion (64 hex chars)
    key_portion = secrets.token_hex(32)
    return f"{prefix}{key_portion}"


def generate_deck_id() -> str:
    """Generate a deck ID with prefix dck_"""
    return f"dck_{secrets.token_hex(8)}"


def generate_card_id() -> str:
    """Generate a flashcard ID with prefix crd_"""
    return f"crd_{secrets.token_hex(8)}"


def generate_session_id() -> str:
    """Generate a session ID with prefix ssn_"""
    return f"ssn_{secrets.token_hex(8)}"


def generate_import_job_id() -> str:
    """Generate an import job ID with prefix imp_"""
    return f"imp_{secrets.token_hex(8)}"


def generate_plan_id() -> str:
    """Generate a learning plan ID with prefix pln_"""
    return f"pln_{secrets.token_hex(8)}"
