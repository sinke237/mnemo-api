"""Ensure API key user foreign key cascades on delete.

Revision ID: 9a1b2c3d4e5f
Revises: 7b2a1d4e9f0c
Create Date: 2026-03-16 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9a1b2c3d4e5f"
down_revision: str | Sequence[str] | None = "7b2a1d4e9f0c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint("fk_api_keys_user_id_users", "api_keys", type_="foreignkey")
    op.create_foreign_key(
        "fk_api_keys_user_id_users",
        "api_keys",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("fk_api_keys_user_id_users", "api_keys", type_="foreignkey")
    op.create_foreign_key(
        "fk_api_keys_user_id_users",
        "api_keys",
        "users",
        ["user_id"],
        ["id"],
    )
