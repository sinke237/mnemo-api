"""
Integration tests for deck and flashcard CRUD.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.core.constants import DEFAULT_DIFFICULTY, PermissionScope
from mnemo.models.card_memory_state import CardMemoryState
from mnemo.models.flashcard import Flashcard
from mnemo.models.user import User
from mnemo.services.api_key import create_api_key


@pytest.fixture
async def user_token(
    db: AsyncSession, client: AsyncClient, authenticated_user: User
) -> tuple[User, str]:
    db.add(authenticated_user)
    await db.flush()

    _, plain_key = await create_api_key(
        db=db,
        user_id=authenticated_user.id,
        name="Deck Key",
        is_live=False,
        scopes=[
            PermissionScope.DECKS_READ,
            PermissionScope.DECKS_WRITE,
            PermissionScope.PROGRESS_READ,
        ],
    )
    await db.flush()

    token_response = await client.post(
        "/v1/auth/token",
        json={"user_id": authenticated_user.id, "api_key": plain_key},
    )
    assert token_response.status_code == 200
    token = token_response.json()["access_token"]
    return authenticated_user, token


@pytest.mark.asyncio
async def test_deck_card_crud_flow(client: AsyncClient, user_token: tuple[User, str]) -> None:
    _, token = user_token
    headers = {"Authorization": f"Bearer {token}"}

    create_deck = await client.post(
        "/v1/decks",
        json={"name": "Rust Basics", "description": "Core Rust concepts"},
        headers=headers,
    )
    assert create_deck.status_code == 201
    deck = create_deck.json()
    deck_id = deck["id"]
    assert deck["card_count"] == 0
    assert deck["version"] == 1

    card_ids = []
    for idx in range(5):
        resp = await client.post(
            f"/v1/decks/{deck_id}/cards",
            json={"question": f"Q{idx}", "answer": f"A{idx}"},
            headers=headers,
        )
        assert resp.status_code == 201
        card_ids.append(resp.json()["id"])

    deck_after_cards = await client.get(f"/v1/decks/{deck_id}", headers=headers)
    assert deck_after_cards.status_code == 200
    assert deck_after_cards.json()["version"] == 6

    update_card = await client.patch(
        f"/v1/cards/{card_ids[0]}",
        json={"question": "Q0 updated"},
        headers=headers,
    )
    assert update_card.status_code == 200

    delete_card = await client.delete(f"/v1/cards/{card_ids[1]}", headers=headers)
    assert delete_card.status_code == 200

    deck_resp = await client.get(f"/v1/decks/{deck_id}", headers=headers)
    assert deck_resp.status_code == 200
    deck_data = deck_resp.json()
    assert deck_data["card_count"] == 4
    assert deck_data["version"] == 8


@pytest.mark.asyncio
async def test_deck_name_conflict(client: AsyncClient, user_token: tuple[User, str]) -> None:
    _, token = user_token
    headers = {"Authorization": f"Bearer {token}"}

    resp1 = await client.post("/v1/decks", json={"name": "Conflicts"}, headers=headers)
    assert resp1.status_code == 201

    resp2 = await client.post("/v1/decks", json={"name": "Conflicts"}, headers=headers)
    assert resp2.status_code == 409
    assert resp2.json()["error"]["code"] == "DECK_NAME_CONFLICT"


@pytest.mark.asyncio
async def test_cascade_delete_deck_cards_memory_state(
    client: AsyncClient, user_token: tuple[User, str], db: AsyncSession
) -> None:
    user, token = user_token
    headers = {"Authorization": f"Bearer {token}"}

    deck_resp = await client.post("/v1/decks", json={"name": "Cascade"}, headers=headers)
    deck_id = deck_resp.json()["id"]

    card_resp = await client.post(
        f"/v1/decks/{deck_id}/cards",
        json={"question": "Q", "answer": "A"},
        headers=headers,
    )
    card_id = card_resp.json()["id"]

    db.add(
        CardMemoryState(
            card_id=card_id,
            user_id=user.id,
            interval_days=1.0,
            ease_factor=2.5,
            repetitions=1,
            streak=1,
        )
    )
    await db.flush()

    delete_resp = await client.delete(f"/v1/decks/{deck_id}", headers=headers)
    assert delete_resp.status_code == 200

    db.expire_all()

    cards = await db.execute(select(Flashcard).where(Flashcard.deck_id == deck_id))
    assert cards.scalars().all() == []

    states = await db.execute(select(CardMemoryState).where(CardMemoryState.card_id == card_id))
    assert states.scalars().all() == []


@pytest.mark.asyncio
async def test_pagination_shape(client: AsyncClient, user_token: tuple[User, str]) -> None:
    _, token = user_token
    headers = {"Authorization": f"Bearer {token}"}

    deck_resp = await client.post("/v1/decks", json={"name": "Paging"}, headers=headers)
    deck_id = deck_resp.json()["id"]

    for idx in range(3):
        resp = await client.post(
            f"/v1/decks/{deck_id}/cards",
            json={"question": f"Q{idx}", "answer": f"A{idx}"},
            headers=headers,
        )
        assert resp.status_code == 201

    cards_resp = await client.get(f"/v1/decks/{deck_id}/cards?page=1&per_page=2", headers=headers)
    assert cards_resp.status_code == 200
    data = cards_resp.json()
    assert data["pagination"]["page"] == 1
    assert data["pagination"]["per_page"] == 2
    assert data["pagination"]["total"] == 3
    assert data["pagination"]["total_pages"] == 2
    assert len(data["data"]) == 2


@pytest.mark.asyncio
async def test_put_flashcard_defaults_and_clear_source_ref(
    client: AsyncClient, user_token: tuple[User, str]
) -> None:
    _, token = user_token
    headers = {"Authorization": f"Bearer {token}"}

    deck_resp = await client.post("/v1/decks", json={"name": "Replace Defaults"}, headers=headers)
    deck_id = deck_resp.json()["id"]

    card_resp = await client.post(
        f"/v1/decks/{deck_id}/cards",
        json={
            "question": "Initial?",
            "answer": "Initial",
            "source_ref": "ref-1",
            "tags": ["t1"],
            "difficulty": 4,
        },
        headers=headers,
    )
    card_id = card_resp.json()["id"]

    replace_resp = await client.put(
        f"/v1/cards/{card_id}",
        json={"question": "Updated?", "answer": "Updated"},
        headers=headers,
    )
    assert replace_resp.status_code == 200
    replaced = replace_resp.json()
    assert replaced["tags"] == []
    assert replaced["difficulty"] == DEFAULT_DIFFICULTY
    assert replaced["source_ref"] is None


@pytest.mark.asyncio
async def test_get_deck_stats(client: AsyncClient, user_token: tuple[User, str]) -> None:
    _, token = user_token
    headers = {"Authorization": f"Bearer {token}"}

    create_deck = await client.post(
        "/v1/decks",
        json={"name": "Stats Deck", "description": "Deck for stats test"},
        headers=headers,
    )
    assert create_deck.status_code == 201
    deck_id = create_deck.json()["id"]

    for idx in range(3):
        response = await client.post(
            f"/v1/decks/{deck_id}/cards",
            json={"question": f"Q{idx}", "answer": f"A{idx}"},
            headers=headers,
        )
        assert response.status_code == 201

    stats_resp = await client.get(f"/v1/decks/{deck_id}/stats", headers=headers)
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["deck_id"] == deck_id
    assert stats["name"] == "Stats Deck"
    assert stats["total_cards"] == 3
    assert stats["mastered_cards"] == 0
    assert (
        stats["due_count"] == 0
    )  # Cards just created are not due yet in the system, or need a session to become due
    # Additional DeckProgressResponse fields
    assert "mastery_pct" in stats
    assert isinstance(stats["mastery_pct"], float)
    assert stats["mastery_pct"] == 0.0
    assert "accuracy_rate" in stats
    assert isinstance(stats["accuracy_rate"], float)
    assert stats["accuracy_rate"] == 0.0
    assert "total_sessions" in stats
    assert isinstance(stats["total_sessions"], int)
    assert stats["total_sessions"] == 0
    assert "last_studied_at" in stats
    assert stats["last_studied_at"] is None
    assert "last_studied_at_local" in stats
    assert stats["last_studied_at_local"] is None


@pytest.mark.asyncio
async def test_idempotency_key_replay(client: AsyncClient, user_token: tuple[User, str]) -> None:
    _, token = user_token
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-test-key"}

    first = await client.post("/v1/decks", json={"name": "Idem"}, headers=headers)
    assert first.status_code == 201
    first_body = first.json()

    second = await client.post("/v1/decks", json={"name": "Idem"}, headers=headers)
    assert second.status_code == 201
    assert second.json() == first_body
