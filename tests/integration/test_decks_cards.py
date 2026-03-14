"""
Integration tests for deck and flashcard CRUD.
"""

from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.core.constants import PermissionScope
from mnemo.db.database import AsyncSessionLocal
from mnemo.models.card_memory_state import CardMemoryState
from mnemo.models.deck import Deck
from mnemo.models.flashcard import Flashcard
from mnemo.models.user import User
from mnemo.schemas.user import UserCreate
from mnemo.services.api_key import create_api_key
from mnemo.services.user import create_user


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        await session.execute(delete(CardMemoryState))
        await session.execute(delete(Flashcard))
        await session.execute(delete(Deck))
        await session.execute(delete(User))
        await session.commit()
        yield session
        await session.execute(delete(CardMemoryState))
        await session.execute(delete(Flashcard))
        await session.execute(delete(Deck))
        await session.execute(delete(User))
        await session.commit()


@pytest.fixture
async def user_token(db_session: AsyncSession, client: AsyncClient) -> tuple[User, str]:
    user_data = UserCreate(
        display_name="Deck User",
        country="US",
        timezone="America/New_York",
        locale="en-US",
        preferred_language="en",
        daily_goal_cards=20,
    )
    user = await create_user(db_session, user_data)

    _, plain_key = await create_api_key(
        db=db_session,
        user_id=user.id,
        name="Deck Key",
        is_live=False,
        scopes=[
            PermissionScope.DECKS_READ,
            PermissionScope.DECKS_WRITE,
            PermissionScope.PROGRESS_READ,
        ],
    )
    await db_session.commit()

    token_response = await client.post(
        "/v1/auth/token",
        json={"user_id": user.id, "api_key": plain_key},
    )
    assert token_response.status_code == 200
    token = token_response.json()["access_token"]
    return user, token


@pytest.mark.asyncio
async def test_deck_card_crud_flow(client: AsyncClient, user_token: tuple[User, str]) -> None:
    _, token = user_token
    headers = {"Authorization": f"Bearer {token}"}

    # Create deck
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

    # Add 5 cards
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
    deck_after_cards_data = deck_after_cards.json()
    assert deck_after_cards_data["version"] == 6

    # Update one card
    update_card = await client.patch(
        f"/v1/cards/{card_ids[0]}",
        json={"question": "Q0 updated"},
        headers=headers,
    )
    assert update_card.status_code == 200

    # Delete one card
    delete_card = await client.delete(
        f"/v1/cards/{card_ids[1]}",
        headers=headers,
    )
    assert delete_card.status_code == 204

    # Verify card_count is correct
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
    client: AsyncClient, user_token: tuple[User, str], db_session: AsyncSession
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

    # Insert a memory state row manually
    db_session.add(
        CardMemoryState(
            card_id=card_id,
            user_id=user.id,
            interval_days=1.0,
            ease_factor=2.5,
            repetitions=1,
            streak=1,
        )
    )
    await db_session.commit()

    delete_resp = await client.delete(f"/v1/decks/{deck_id}", headers=headers)
    assert delete_resp.status_code == 204

    db_session.expire_all()

    cards = await db_session.execute(select(Flashcard).where(Flashcard.deck_id == deck_id))
    assert cards.scalars().all() == []

    states = await db_session.execute(
        select(CardMemoryState).where(CardMemoryState.card_id == card_id)
    )
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
    assert "data" in data
    assert "pagination" in data
    assert data["pagination"]["page"] == 1
    assert data["pagination"]["per_page"] == 2
    assert data["pagination"]["total"] == 3
    assert data["pagination"]["total_pages"] == 2
    assert len(data["data"]) == 2


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
