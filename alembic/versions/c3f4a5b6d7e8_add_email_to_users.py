"""Add email fields and normalize user authentication

Revision ID: add_email_to_users
Revises: 7ada38a5dbc7
Create Date: 2026-03-29 12:00:00.000000

This migration:
1. Adds email, normalized_email, email_verified, email_verified_at fields
2. Backfills existing users with placeholder emails (MANUAL ACTION REQUIRED)
3. Makes email NOT NULL after backfill
4. Adds unique constraints and indexes
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_email_to_users"
down_revision: str | Sequence[str] | None = "7ada38a5dbc7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add email fields to users table."""

    # Step 1: Add email fields as NULLABLE first
    op.add_column("users", sa.Column("email", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("normalized_email", sa.String(length=255), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "email_verified",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "email_verified_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # Step 2: Backfill existing users with placeholder emails
    # IMPORTANT: In production, you should update these with real emails before making NOT NULL
    # Format: user_{id}@placeholder.mnemo.local
    # Use a dialect-agnostic, batched update to avoid relying on CONCAT() and to reduce
    # long-running locks on large tables (works on SQLite, Postgres, MySQL, etc.).
    conn = op.get_bind()
    users_table = sa.table(
        "users",
        sa.column("id", sa.String),
        sa.column("email", sa.String),
        sa.column("normalized_email", sa.String),
    )

    batch_size = 1000
    while True:
        ids = [row[0] for row in conn.execute(
            sa.select(users_table.c.id).where(users_table.c.email.is_(None)).limit(batch_size)
        ).fetchall()]
        if not ids:
            break

        # Perform per-id parameterised updates to avoid SQL dialect-specific concat
        for uid in ids:
            placeholder = f"user_{uid}@placeholder.mnemo.local"
            conn.execute(
                sa.update(users_table)
                .where(users_table.c.id == uid)
                .values(email=placeholder, normalized_email=placeholder)
            )

    # Step 3: Make email fields NOT NULL after backfill
    op.alter_column("users", "email", nullable=False)
    op.alter_column("users", "normalized_email", nullable=False)

    # Step 4: Add unique constraints and indexes
    op.create_unique_constraint("uq_users_email", "users", ["email"])
    op.create_unique_constraint("uq_users_normalized_email", "users", ["normalized_email"])


def downgrade() -> None:
    """Remove email fields from users table."""
    op.drop_constraint("uq_users_normalized_email", "users", type_="unique")
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.drop_column("users", "email_verified_at")
    op.drop_column("users", "email_verified")
    op.drop_column("users", "normalized_email")
    op.drop_column("users", "email")
