"""
Integration tests for the study plan endpoints.
  POST /v1/users/{id}/plan — generate schedule      (sessions:run scope)
  GET  /v1/users/{id}/plan — retrieve active plan   (progress:read scope)

Covers:
- Happy-path plan generation and retrieval
- Schedule dates are in the user's local timezone (FR-07.2)
- 404 when generating with an unknown deck
- 404 when no plan exists yet (GET before POST)
- 403 when accessing another user's plan
- 403 when missing required scope
- 422 for out-of-range `days` values
"""

import uuid
from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.core.constants import PermissionScope
from mnemo.main import app
from mnemo.models.user import User
from mnemo.schemas.user import UserCreate
from mnemo.services.api_key import create_api_key
from mnemo.services.deck import create_deck
from mnemo.services.user import create_user

# `db_session` fixture is provided by tests.test_fixtures
# `client`, `db`, `authenticated_user` fixtures are from tests.test_fixtures


# ── helpers ───────────────────────────────────────────────────────────────────


async def _make_user_with_key(
    db: AsyncSession,
    country: str,
    timezone: str,
    scopes: list[PermissionScope],
) -> tuple[User, str]:
    """Create a user + API key, return (user, plain_api_key)."""
    user_data = UserCreate(
        display_name="Plan Tester",
        country=country,
        timezone=timezone,
        preferred_language="en",
        daily_goal_cards=20,
    )
    user = await create_user(db, user_data)
    _, plain_key = await create_api_key(
        db=db,
        user_id=user.id,
        name=f"plan-key-{uuid.uuid4().hex[:8]}",
        is_live=False,
        scopes=scopes,
    )
    await db.commit()
    return user, plain_key


async def _get_token(client: AsyncClient, user_id: str, api_key: str) -> str:
    resp = await client.post("/v1/auth/token", json={"user_id": user_id, "api_key": api_key})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


# ── fixture ───────────────────────────────────────────────────────────────────


@pytest.fixture
async def plan_client(db_session: AsyncSession) -> AsyncClient:
    """
    HTTP client backed by the real app.

    Note: the `db_session` fixture (used here) overrides the application
    dependency `get_db` — see `tests/test_fixtures.py` for the override.
    This fixture (`plan_client`) merely wraps the ASGI transport and does
    not change DB dependency wiring.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


# ── happy path ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_and_retrieve_plan(
    plan_client: AsyncClient, db_session: AsyncSession
) -> None:
    """POST generates a valid plan; GET returns the same plan."""
    user, api_key = await _make_user_with_key(
        db_session,
        country="CM",
        timezone="Africa/Douala",
        scopes=[PermissionScope.SESSIONS_RUN, PermissionScope.PROGRESS_READ],
    )
    token = await _get_token(plan_client, user.id, api_key)
    headers = {"Authorization": f"Bearer {token}"}

    # Create a deck with cards
    deck = await create_deck(
        db=db_session,
        user_id=user.id,
        name="OAuth 2.0",
        description=None,
        tags=[],
    )
    # Manually set card_count so the schedule calculation has something to work with
    deck.card_count = 14
    await db_session.commit()

    # POST /plan
    resp = await plan_client.post(
        f"/v1/users/{user.id}/plan",
        json={"deck_id": deck.id, "goal": "Pass OAuth cert", "days": 7, "daily_minutes": 30},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()

    assert body["plan_id"].startswith("pln_")
    assert body["deck_id"] == deck.id
    assert body["goal"] == "Pass OAuth cert"
    assert body["days"] == 7
    assert body["daily_target"] >= 1
    assert body["daily_minutes"] == 30
    assert len(body["schedule"]) == 7

    # Schedule days must be numbered 1..7
    for i, entry in enumerate(body["schedule"], start=1):
        assert entry["day"] == i
        assert len(entry["date"]) == 10  # YYYY-MM-DD
        assert entry["cards_to_study"] >= 1
        assert isinstance(entry["focus"], str)

    plan_id = body["plan_id"]

    # GET /plan must return the same plan
    resp2 = await plan_client.get(f"/v1/users/{user.id}/plan", headers=headers)
    assert resp2.status_code == 200, resp2.text
    body2 = resp2.json()
    assert body2["plan_id"] == plan_id
    assert body2["schedule"] == body["schedule"]


@pytest.mark.asyncio
async def test_generate_plan_replaces_active(
    plan_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Generating a second plan means GET returns the newest one (days=3)."""
    user, api_key = await _make_user_with_key(
        db_session,
        country="NG",
        timezone="Africa/Lagos",
        scopes=[PermissionScope.SESSIONS_RUN, PermissionScope.PROGRESS_READ],
    )
    token = await _get_token(plan_client, user.id, api_key)
    headers = {"Authorization": f"Bearer {token}"}

    deck = await create_deck(
        db=db_session, user_id=user.id, name="Deck A", description=None, tags=[]
    )
    deck.card_count = 10
    await db_session.commit()

    # First plan — 5 days
    resp1 = await plan_client.post(
        f"/v1/users/{user.id}/plan",
        json={"deck_id": deck.id, "days": 5, "daily_minutes": 20},
        headers=headers,
    )
    assert resp1.status_code == 201

    # Second plan — 3 days (distinctly different)
    resp2 = await plan_client.post(
        f"/v1/users/{user.id}/plan",
        json={"deck_id": deck.id, "goal": "Second plan", "days": 3, "daily_minutes": 15},
        headers=headers,
    )
    assert resp2.status_code == 201
    new_plan_id = resp2.json()["plan_id"]

    get_resp = await plan_client.get(f"/v1/users/{user.id}/plan", headers=headers)
    assert get_resp.status_code == 200
    # The most recently created plan must be returned
    assert get_resp.json()["plan_id"] == new_plan_id
    assert get_resp.json()["days"] == 3


# ── schedule date timezone tests (FR-07.2) ────────────────────────────────────


@pytest.mark.asyncio
async def test_schedule_dates_reflect_user_local_timezone(
    plan_client: AsyncClient, db_session: AsyncSession
) -> None:
    """
    Dates in the schedule must be calendar dates in the user's local timezone,
    not UTC dates (FR-07.2). We verify the first date is a valid YYYY-MM-DD
    string and that all consecutive dates are one day apart.
    """
    user, api_key = await _make_user_with_key(
        db_session,
        country="KE",
        timezone="Africa/Nairobi",  # UTC+3
        scopes=[PermissionScope.SESSIONS_RUN, PermissionScope.PROGRESS_READ],
    )
    token = await _get_token(plan_client, user.id, api_key)
    headers = {"Authorization": f"Bearer {token}"}

    deck = await create_deck(
        db=db_session, user_id=user.id, name="Swahili Vocab", description=None, tags=[]
    )
    deck.card_count = 21
    await db_session.commit()

    resp = await plan_client.post(
        f"/v1/users/{user.id}/plan",
        json={"deck_id": deck.id, "days": 7, "daily_minutes": 30},
        headers=headers,
    )
    assert resp.status_code == 201
    schedule = resp.json()["schedule"]

    # All dates must be valid YYYY-MM-DD
    dates = [date.fromisoformat(e["date"]) for e in schedule]

    # Consecutive dates must differ by exactly 1 day
    for i in range(1, len(dates)):
        assert (
            dates[i] - dates[i - 1]
        ).days == 1, f"Day {i+1} date {dates[i]} is not consecutive with {dates[i-1]}"


# ── error cases ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_plan_unknown_deck_returns_404(
    plan_client: AsyncClient, db_session: AsyncSession
) -> None:
    user, api_key = await _make_user_with_key(
        db_session,
        country="GH",
        timezone="Africa/Accra",
        scopes=[PermissionScope.SESSIONS_RUN],
    )
    token = await _get_token(plan_client, user.id, api_key)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await plan_client.post(
        f"/v1/users/{user.id}/plan",
        json={"deck_id": "dck_doesnotexist", "days": 5, "daily_minutes": 30},
        headers=headers,
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "DECK_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_plan_before_any_generated_returns_404(
    plan_client: AsyncClient, db_session: AsyncSession
) -> None:
    user, api_key = await _make_user_with_key(
        db_session,
        country="ZA",
        timezone="Africa/Johannesburg",
        scopes=[PermissionScope.PROGRESS_READ],
    )
    token = await _get_token(plan_client, user.id, api_key)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await plan_client.get(f"/v1/users/{user.id}/plan", headers=headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "PLAN_NOT_FOUND"


@pytest.mark.asyncio
async def test_generate_plan_wrong_user_returns_403(
    plan_client: AsyncClient, db_session: AsyncSession
) -> None:
    """A user cannot generate a plan on behalf of another user."""
    user_a, api_key_a = await _make_user_with_key(
        db_session,
        country="US",
        timezone="America/New_York",
        scopes=[PermissionScope.SESSIONS_RUN],
    )
    user_b, _ = await _make_user_with_key(
        db_session,
        country="FR",
        timezone="Europe/Paris",
        scopes=[PermissionScope.SESSIONS_RUN],
    )

    token_a = await _get_token(plan_client, user_a.id, api_key_a)
    headers_a = {"Authorization": f"Bearer {token_a}"}

    resp = await plan_client.post(
        f"/v1/users/{user_b.id}/plan",
        json={"deck_id": "dck_any", "days": 5, "daily_minutes": 30},
        headers=headers_a,
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "INSUFFICIENT_SCOPE"


@pytest.mark.asyncio
async def test_get_plan_wrong_user_returns_403(
    plan_client: AsyncClient, db_session: AsyncSession
) -> None:
    user_a, api_key_a = await _make_user_with_key(
        db_session,
        country="BR",
        timezone="America/Sao_Paulo",
        scopes=[PermissionScope.PROGRESS_READ],
    )
    user_b, _ = await _make_user_with_key(
        db_session,
        country="JP",
        timezone="Asia/Tokyo",
        scopes=[PermissionScope.PROGRESS_READ],
    )

    token_a = await _get_token(plan_client, user_a.id, api_key_a)
    headers_a = {"Authorization": f"Bearer {token_a}"}

    resp = await plan_client.get(f"/v1/users/{user_b.id}/plan", headers=headers_a)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "INSUFFICIENT_SCOPE"


@pytest.mark.asyncio
async def test_generate_plan_missing_scope_returns_403(
    plan_client: AsyncClient, db_session: AsyncSession
) -> None:
    """POST /plan requires sessions:run; progress:read alone must be rejected."""
    user, api_key = await _make_user_with_key(
        db_session,
        country="DE",
        timezone="Europe/Berlin",
        scopes=[PermissionScope.PROGRESS_READ],  # missing sessions:run
    )
    token = await _get_token(plan_client, user.id, api_key)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await plan_client.post(
        f"/v1/users/{user.id}/plan",
        json={"deck_id": "dck_any", "days": 5, "daily_minutes": 30},
        headers=headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_plan_missing_scope_returns_403(
    plan_client: AsyncClient, db_session: AsyncSession
) -> None:
    """GET /plan requires progress:read; sessions:run alone must be rejected."""
    user, api_key = await _make_user_with_key(
        db_session,
        country="IN",
        timezone="Asia/Kolkata",
        scopes=[PermissionScope.SESSIONS_RUN],  # missing progress:read
    )
    token = await _get_token(plan_client, user.id, api_key)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await plan_client.get(f"/v1/users/{user.id}/plan", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_generate_plan_days_validation(
    plan_client: AsyncClient, db_session: AsyncSession
) -> None:
    """days must be 1–365; out-of-range values must return 422."""
    user, api_key = await _make_user_with_key(
        db_session,
        country="AU",
        timezone="Australia/Sydney",
        scopes=[PermissionScope.SESSIONS_RUN],
    )
    token = await _get_token(plan_client, user.id, api_key)
    headers = {"Authorization": f"Bearer {token}"}

    for bad_days in (0, 366):
        resp = await plan_client.post(
            f"/v1/users/{user.id}/plan",
            json={"deck_id": "dck_any", "days": bad_days, "daily_minutes": 30},
            headers=headers,
        )
        assert resp.status_code == 422, f"Expected 422 for days={bad_days}, got {resp.status_code}"


@pytest.mark.asyncio
async def test_generate_plan_days_boundaries(
    plan_client: AsyncClient, db_session: AsyncSession
) -> None:
    """days at the inclusive boundaries 1 and 365 must be accepted (201)."""
    user, api_key = await _make_user_with_key(
        db_session,
        country="US",
        timezone="America/New_York",
        scopes=[PermissionScope.SESSIONS_RUN],
    )
    token = await _get_token(plan_client, user.id, api_key)
    headers = {"Authorization": f"Bearer {token}"}

    deck = await create_deck(
        db=db_session, user_id=user.id, name="Boundary Deck", description=None, tags=[]
    )
    deck.card_count = 10
    await db_session.commit()

    for valid_days in (1, 365):
        resp = await plan_client.post(
            f"/v1/users/{user.id}/plan",
            json={"deck_id": deck.id, "days": valid_days, "daily_minutes": 30},
            headers=headers,
        )
        assert (
            resp.status_code == 201
        ), f"Expected 201 for days={valid_days}, got {resp.status_code}"
