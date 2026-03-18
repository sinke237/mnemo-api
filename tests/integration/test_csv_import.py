"""
Integration tests for CSV import flow.
"""

from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.core.constants import PermissionScope
from mnemo.db.database import AsyncSessionLocal
from mnemo.models.card_memory_state import CardMemoryState
from mnemo.models.deck import Deck
from mnemo.models.flashcard import Flashcard
from mnemo.models.import_job import ImportJob
from mnemo.models.user import User
from mnemo.schemas.user import UserCreate
from mnemo.services import import_job as import_service
from mnemo.services.api_key import create_api_key
from mnemo.services.user import create_user


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        await session.execute(delete(CardMemoryState))
        await session.execute(delete(Flashcard))
        await session.execute(delete(ImportJob))
        await session.execute(delete(Deck))
        await session.execute(delete(User))
        await session.commit()
        yield session
        await session.execute(delete(CardMemoryState))
        await session.execute(delete(Flashcard))
        await session.execute(delete(ImportJob))
        await session.execute(delete(Deck))
        await session.execute(delete(User))
        await session.commit()


@pytest.fixture
async def user_token(db_session: AsyncSession, client: AsyncClient) -> tuple[User, str]:
    user_data = UserCreate(
        display_name="Import User",
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
        name="Import Key",
        is_live=False,
        scopes=[
            PermissionScope.IMPORT_WRITE,
            PermissionScope.DECKS_READ,
            PermissionScope.DECKS_WRITE,
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


async def _process_job(job_id: str) -> None:
    async with AsyncSessionLocal() as session:
        await import_service.process_import_job(session, job_id)
        await session.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "csv_text",
    [
        "What does ASPSP stand for?,Account Servicing Payment Service Provider.\n",
        "question,answer\nWhat does ASPSP stand for?,Account Servicing Payment Service Provider.\n",
        '"Consent Status: Received","The consent request is technically correct..."\n',
    ],
)
async def test_csv_import_formats(
    client: AsyncClient, user_token: tuple[User, str], csv_text: str
) -> None:
    _, token = user_token
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/v1/import/csv",
        headers=headers,
        files={"file": ("cards.csv", csv_text, "text/csv")},
        data={"deck_name": "CSV Format Deck", "mode": "merge"},
    )
    assert resp.status_code == 202
    payload = resp.json()
    job_id = payload["job_id"]
    deck_id = payload["deck_id"]

    await _process_job(job_id)

    cards_resp = await client.get(f"/v1/decks/{deck_id}/cards", headers=headers)
    assert cards_resp.status_code == 200
    assert cards_resp.json()["pagination"]["total"] == 1


@pytest.mark.asyncio
async def test_csv_import_merge_mode_skips_duplicates(
    client: AsyncClient, user_token: tuple[User, str]
) -> None:
    _, token = user_token
    headers = {"Authorization": f"Bearer {token}"}

    deck_resp = await client.post(
        "/v1/decks",
        json={"name": "Merge Deck"},
        headers=headers,
    )
    assert deck_resp.status_code == 201
    deck_id = deck_resp.json()["id"]

    first_card = await client.post(
        f"/v1/decks/{deck_id}/cards",
        json={"question": "Q1", "answer": "A1"},
        headers=headers,
    )
    assert first_card.status_code == 201

    csv_text = "Q1,A1\nQ2,A2\n"
    resp = await client.post(
        "/v1/import/csv",
        headers=headers,
        files={"file": ("merge.csv", csv_text, "text/csv")},
        data={"deck_id": deck_id, "mode": "merge"},
    )
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    await _process_job(job_id)

    status = await client.get(f"/v1/import/{job_id}", headers=headers)
    assert status.status_code == 200
    status_payload = status.json()
    assert status_payload["cards_imported"] == 1
    assert status_payload["cards_skipped"] == 1

    cards_resp = await client.get(f"/v1/decks/{deck_id}/cards", headers=headers)
    assert cards_resp.status_code == 200
    assert cards_resp.json()["pagination"]["total"] == 2


@pytest.mark.asyncio
async def test_csv_import_replace_mode(client: AsyncClient, user_token: tuple[User, str]) -> None:
    _, token = user_token
    headers = {"Authorization": f"Bearer {token}"}

    deck_resp = await client.post(
        "/v1/decks",
        json={"name": "Replace Deck"},
        headers=headers,
    )
    assert deck_resp.status_code == 201
    deck_id = deck_resp.json()["id"]

    old_card_resp = await client.post(
        f"/v1/decks/{deck_id}/cards",
        json={"question": "Old Q", "answer": "Old A"},
        headers=headers,
    )
    assert old_card_resp.status_code == 201

    csv_text = "New Q,New A\nAnother Q,Another A\n"
    resp = await client.post(
        "/v1/import/csv",
        headers=headers,
        files={"file": ("replace.csv", csv_text, "text/csv")},
        data={"deck_id": deck_id, "mode": "replace"},
    )
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    await _process_job(job_id)

    cards_resp = await client.get(f"/v1/decks/{deck_id}/cards", headers=headers)
    assert cards_resp.status_code == 200
    assert cards_resp.json()["pagination"]["total"] == 2


@pytest.mark.asyncio
async def test_csv_import_oversized_file_rejected(
    client: AsyncClient, user_token: tuple[User, str]
) -> None:
    _, token = user_token
    headers = {"Authorization": f"Bearer {token}"}

    oversized = "Q,A\n" + ("x" * (5 * 1024 * 1024))
    resp = await client.post(
        "/v1/import/csv",
        headers=headers,
        files={"file": ("big.csv", oversized, "text/csv")},
        data={"deck_name": "Oversize Deck", "mode": "merge"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_CSV_FORMAT"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "csv_text",
    [
        "Q1,A1\nQ2,A2",  # Comma
        "Q1;A1\nQ2;A2",  # Semicolon
        "Q1\tA1\nQ2\tA2",  # Tab
    ],
)
async def test_csv_import_with_different_delimiters(
    client: AsyncClient, user_token: tuple[User, str], csv_text: str
) -> None:
    _, token = user_token
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/v1/import/csv",
        headers=headers,
        files={"file": ("cards.csv", csv_text, "text/csv")},
        data={"deck_name": "Delimiter Deck", "mode": "merge"},
    )
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]
    deck_id = resp.json()["deck_id"]

    await _process_job(job_id)

    cards_resp = await client.get(f"/v1/decks/{deck_id}/cards", headers=headers)
    assert cards_resp.status_code == 200
    assert cards_resp.json()["pagination"]["total"] == 2
