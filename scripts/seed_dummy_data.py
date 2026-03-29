"""Seed dummy users, API keys, decks, and cards using application services.

This is intended for local development only.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import delete, select

from mnemo.core.constants import PermissionScope
from mnemo.db.database import AsyncSessionLocal
from mnemo.models.user import User
from mnemo.schemas.user import UserProvisionRequest
from mnemo.services import deck as deck_service
from mnemo.services import flashcard as flashcard_service
from mnemo.services.api_key import create_api_key
from mnemo.services.user import provision_user

SEED_DISPLAY_NAMES = ["Seed Admin", "Seed User 1", "Seed User 2"]
SEED_DOC_PATH = Path("dev_docs/seed_data.md")


async def _delete_seed_users() -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(delete(User).where(User.display_name.in_(SEED_DISPLAY_NAMES)))
        await session.commit()


async def _seed_users_exist() -> bool:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User.id).where(User.display_name.in_(SEED_DISPLAY_NAMES)).limit(1)
        )
        return result.scalar_one_or_none() is not None


async def _seed_data() -> dict[str, str]:
    async with AsyncSessionLocal() as session:
        admin, admin_key, _ = await provision_user(
            db=session,
            email="seed_admin@example.com",
            password="Password123",
            display_name="Seed Admin",
            country="US",
            timezone="America/New_York",
            locale="en-US",
            preferred_language="en",
            daily_goal_cards=20,
            role="admin",
            create_live_key=True,
        )
        user1, user1_key, _ = await provision_user(
            db=session,
            email="seed_user1@example.com",
            password="Password123",
            display_name="Seed User 1",
            country="CM",
            timezone="Africa/Douala",
            locale="fr-CM",
            preferred_language="fr",
            daily_goal_cards=25,
            create_live_key=False,
        )
        user2, user2_key, _ = await provision_user(
            db=session,
            email="seed_user2@example.com",
            password="Password123",
            display_name="Seed User 2",
            country="GB",
            timezone="Europe/London",
            locale="en-GB",
            preferred_language="en",
            daily_goal_cards=30,
            create_live_key=False,
        )

        deck1 = await deck_service.create_deck(
            session,
            user_id=admin.id,
            name="Seed Deck - Basics",
            description="Starter deck with example cards",
            tags=["seed", "basics"],
        )
        deck2 = await deck_service.create_deck(
            session,
            user_id=admin.id,
            name="Seed Deck - Empty",
            description="Empty deck for manual testing",
            tags=["seed"],
        )
        deck3 = await deck_service.create_deck(
            session,
            user_id=user1.id,
            name="Second User Deck",
            description="Deck owned by regular seed user",
            tags=["seed", "second"],
        )

        card1 = await flashcard_service.create_card(
            session,
            user_id=admin.id,
            deck_id=deck1.id,
            question="What does API stand for?",
            answer="Application Programming Interface",
            source_ref=None,
            tags=["seed"],
            difficulty=3,
        )
        card2 = await flashcard_service.create_card(
            session,
            user_id=admin.id,
            deck_id=deck1.id,
            question="What is HTTP?",
            answer="Hypertext Transfer Protocol",
            source_ref=None,
            tags=["seed"],
            difficulty=3,
        )
        card3 = await flashcard_service.create_card(
            session,
            user_id=admin.id,
            deck_id=deck1.id,
            question="What does CRUD stand for?",
            answer="Create, Read, Update, Delete",
            source_ref=None,
            tags=["seed", "basics"],
            difficulty=2,
        )
        card4 = await flashcard_service.create_card(
            session,
            user_id=admin.id,
            deck_id=deck1.id,
            question="What is REST?",
            answer="Representational State Transfer",
            source_ref=None,
            tags=["seed", "basics"],
            difficulty=3,
        )
        card5 = await flashcard_service.create_card(
            session,
            user_id=admin.id,
            deck_id=deck1.id,
            question="What is JSON?",
            answer="JavaScript Object Notation",
            source_ref=None,
            tags=["seed", "basics"],
            difficulty=1,
        )

        card6 = await flashcard_service.create_card(
            session,
            user_id=user1.id,
            deck_id=deck3.id,
            question="What is a deck?",
            answer="A named collection of flashcards.",
            source_ref=None,
            tags=["seed", "second"],
            difficulty=2,
        )
        card7 = await flashcard_service.create_card(
            session,
            user_id=user1.id,
            deck_id=deck3.id,
            question="What is a flashcard?",
            answer="A single question-answer pair.",
            source_ref=None,
            tags=["seed", "second"],
            difficulty=2,
        )
        card8 = await flashcard_service.create_card(
            session,
            user_id=user1.id,
            deck_id=deck3.id,
            question="What is spaced repetition?",
            answer="A learning technique that schedules reviews to improve retention.",
            source_ref=None,
            tags=["seed", "second"],
            difficulty=3,
        )

        await session.commit()

        return {
            "admin_id": admin.id,
            "user1_id": user1.id,
            "user2_id": user2.id,
            "admin_key": admin_key,
            "user1_key": user1_key,
            "user2_key": user2_key,
            "deck1_id": deck1.id,
            "deck2_id": deck2.id,
            "deck3_id": deck3.id,
            "card1_id": card1.id,
            "card2_id": card2.id,
            "card3_id": card3.id,
            "card4_id": card4.id,
            "card5_id": card5.id,
            "card6_id": card6.id,
            "card7_id": card7.id,
            "card8_id": card8.id,
        }


def _write_seed_doc(data: dict[str, str]) -> None:
    SEED_DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    content = f"""# Seed Data (Auto-Generated via Migrations + Seeder)

These records are inserted automatically when you run `alembic upgrade head` and the
seed script runs (including via Docker Compose startup).

## Users

- `{data['admin_id']}` — Seed Admin (US, America/New_York)
- `{data['user1_id']}` — Seed User 1 (CM, Africa/Douala)
- `{data['user2_id']}` — Seed User 2 (GB, Europe/London)

## API Keys

Each key is bound to the user listed below.

- Admin (`{data['admin_id']}`)
  - `{data['admin_key']}`
- Regular (`{data['user1_id']}`)
  - `{data['user1_key']}`
- Regular (`{data['user2_id']}`)
  - `{data['user2_key']}`

## Decks

- `{data['deck1_id']}` — Seed Deck - Basics (Admin)
- `{data['deck2_id']}` — Seed Deck - Empty (Admin)
- `{data['deck3_id']}` — Second User Deck (Seed User 1)

## Cards

Deck `{data['deck1_id']}`:
- `{data['card1_id']}` — What does API stand for?
- `{data['card2_id']}` — What is HTTP?
- `{data['card3_id']}` — What does CRUD stand for?
- `{data['card4_id']}` — What is REST?
- `{data['card5_id']}` — What is JSON?

Deck `{data['deck3_id']}`:
- `{data['card6_id']}` — What is a deck?
- `{data['card7_id']}` — What is a flashcard?
- `{data['card8_id']}` — What is spaced repetition?
"""
    SEED_DOC_PATH.write_text(content, encoding="utf-8")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed dummy data for development")
    parser.add_argument(
        "--ensure-doc",
        action="store_true",
        help="Only seed when dev_docs/seed_data.md is missing",
    )
    args = parser.parse_args()

    if args.ensure_doc and SEED_DOC_PATH.exists():
        if await _seed_users_exist():
            return

    try:
        await _delete_seed_users()
        data = await _seed_data()
        _write_seed_doc(data)
    except Exception as exc:  # noqa: BLE001 - surface a clear seeding failure and exit
        print(f"Seeding failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
