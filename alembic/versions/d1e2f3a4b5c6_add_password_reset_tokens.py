"""add_password_reset_tokens

Revision ID: d1e2f3a4b5c6
Revises: add_email_to_users
Create Date: 2026-03-29 12:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: str | Sequence[str] | None = "add_email_to_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column("token_hash", sa.String(length=128), nullable=False, index=True),
        sa.Column(
            "user_id",
            sa.String(length=32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_address", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("password_reset_tokens")
