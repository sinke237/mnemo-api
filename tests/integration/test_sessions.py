import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.models import Deck, Flashcard


@pytest.fixture
async def deck_and_cards(db: AsyncSession, authenticated_user):
    db.add(authenticated_user)
    await db.flush()

    deck = Deck(
        id=f"dck_{uuid.uuid4().hex[:24]}",
        name="Test Deck",
        user_id=authenticated_user.id,
    )
    cards = [
        Flashcard(
            id=f"crd_{uuid.uuid4().hex[:24]}",
            deck_id=deck.id,
            question=f"Question {i}",
            answer=f"Answer {i}",
        )
        for i in range(5)
    ]
    db.add(deck)
    db.add_all(cards)
    await db.flush()
    return deck, cards


@pytest.mark.asyncio
async def test_start_session_not_found(client: AsyncClient):
    response = await client.post(
        "/v1/sessions/",
        json={"deck_id": str(uuid.uuid4())},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_session_lifecycle(
    client: AsyncClient,
    db: AsyncSession,
    authenticated_user,
    deck_and_cards,
):
    deck, cards = deck_and_cards

    # Start session
    response = await client.post(
        "/v1/sessions/",
        json={"deck_id": str(deck.id)},
    )
    assert response.status_code == 201
    session = response.json()
    session_id = session["session_id"]
    current_answer = session["current_card"]["answer"]

    # Get session
    response = await client.get(f"/v1/sessions/{session_id}")
    assert response.status_code == 200
    assert response.json()["cards_total"] == 5

    # Answer all cards correctly using the actual card answer
    for _ in range(5):
        response = await client.post(
            f"/v1/sessions/{session_id}/answer",
            json={"answer": current_answer},
        )
        assert response.status_code == 200
        result = response.json()
        assert result["is_correct"]
        if result["next_card"]:
            current_answer = result["next_card"]["answer"]

    # Skip should fail — session is ended
    response = await client.post(f"/v1/sessions/{session_id}/skip")
    assert response.status_code == 409

    # End session
    response = await client.post(f"/v1/sessions/{session_id}/end")
    assert response.status_code == 200

    # Get summary
    response = await client.get(f"/v1/sessions/{session_id}/summary")
    assert response.status_code == 200
    summary = response.json()
    assert summary["correct_answers"] == 5
    assert summary["status"] == "ended"
