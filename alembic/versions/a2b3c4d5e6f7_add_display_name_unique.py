"""add_display_name_unique

Revision ID: a2b3c4d5e6f7
Revises: c0a1b2c3d4e5
Create Date: 2026-03-27 10:30:00.000000

Adds a unique constraint on users.display_name.
NULL values are permitted (multiple users may have no display_name),
because SQL UNIQUE constraints treat NULLs as distinct.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a2b3c4d5e6f7"
down_revision: str | None = "c0a1b2c3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create a unique constraint on display_name.
    # NULLs do not violate UNIQUE in PostgreSQL or SQLite.
    op.create_unique_constraint("uq_users_display_name", "users", ["display_name"])


def downgrade() -> None:
    op.drop_constraint("uq_users_display_name", "users", type_="unique")
