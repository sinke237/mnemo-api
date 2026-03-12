"""
Tests for ID generation utilities.
"""

from mnemo.utils.id_generator import (
    generate_api_key,
    generate_card_id,
    generate_deck_id,
    generate_import_job_id,
    generate_plan_id,
    generate_session_id,
    generate_user_id,
)


def test_generate_user_id() -> None:
    """User IDs should start with usr_ and be 20 chars total"""
    user_id = generate_user_id()
    assert user_id.startswith("usr_")
    assert len(user_id) == 20  # usr_ (4) + 16 hex chars


def test_generate_api_key_test() -> None:
    """Test API keys should start with mnm_test_"""
    key = generate_api_key(is_live=False)
    assert key.startswith("mnm_test_")
    assert len(key) > 40  # mnm_test_ (9) + 64 hex chars


def test_generate_api_key_live() -> None:
    """Live API keys should start with mnm_live_"""
    key = generate_api_key(is_live=True)
    assert key.startswith("mnm_live_")
    assert len(key) > 40


def test_generate_deck_id() -> None:
    """Deck IDs should start with dck_"""
    deck_id = generate_deck_id()
    assert deck_id.startswith("dck_")
    assert len(deck_id) == 20


def test_generate_card_id() -> None:
    """Card IDs should start with crd_"""
    card_id = generate_card_id()
    assert card_id.startswith("crd_")
    assert len(card_id) == 20


def test_generate_session_id() -> None:
    """Session IDs should start with ssn_"""
    session_id = generate_session_id()
    assert session_id.startswith("ssn_")
    assert len(session_id) == 20


def test_generate_import_job_id() -> None:
    """Import job IDs should start with imp_"""
    job_id = generate_import_job_id()
    assert job_id.startswith("imp_")
    assert len(job_id) == 20


def test_generate_plan_id() -> None:
    """Plan IDs should start with pln_"""
    plan_id = generate_plan_id()
    assert plan_id.startswith("pln_")
    assert len(plan_id) == 20


def test_ids_are_unique() -> None:
    """Generated IDs should be unique"""
    ids = {generate_user_id() for _ in range(100)}
    assert len(ids) == 100  # All unique
