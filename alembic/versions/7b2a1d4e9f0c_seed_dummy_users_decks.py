"""Seed dummy users, API key, decks, and flashcards for testing

Revision ID: 7b2a1d4e9f0c
Revises: 6f9b2c1a7d4e
Create Date: 2026-03-14 10:30:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "7b2a1d4e9f0c"
down_revision: str | Sequence[str] | None = "6f9b2c1a7d4e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op. Seed data is created by scripts/seed_dummy_data.py in dev."""
    return None


def downgrade() -> None:
    """No-op for seed data migration."""
    return None
