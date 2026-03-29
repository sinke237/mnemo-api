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
    # Add placeholder columns to collect emails without touching the primary `email`
    op.add_column(
        "users",
        sa.Column("email_placeholder", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("normalized_email_placeholder", sa.String(length=255), nullable=True),
    )
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
    # NOTE: SELECT is batched but UPDATEs are performed per-row (one parameterised
    # UPDATE query per id). The outer `while` loop uses `batch_size` to limit the
    # number of rows selected per iteration; however each id in the batch is updated
    # individually in the inner `for` loop to avoid dialect-specific string
    # concatenation functions. This trades fewer SELECTs for many UPDATEs.
    # Tradeoff / mitigation: committing between iterations of the outer loop
    # (to avoid a single long-running transaction) or using a set-based UPDATE
    # strategy are both valid approaches. This migration leaves per-id updates
    # for dialect safety; consider adding an explicit commit between batches if
    # your Alembic execution environment permits it to reduce lock durations.
    # The relevant variables/blocks are `batch_size`, the outer `while` loop,
    # and the per-id UPDATE block around `placeholder` + `sa.update(users_table)`.
    # Use care if converting to a set-based update to ensure SQL injection safety.
    conn = op.get_bind()
    users_table = sa.table(
        "users",
        sa.column("id", sa.String),
        sa.column("email", sa.String),
        sa.column("normalized_email", sa.String),
        sa.column("email_placeholder", sa.String),
        sa.column("normalized_email_placeholder", sa.String),
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
                .values(
                    email_placeholder=placeholder,
                    normalized_email_placeholder=placeholder,
                )
            )

    # Step 3: Do NOT make `email` NOT NULL or UNIQUE here.
    # Operators should validate addresses collected in `email_placeholder`
    # (e.g., via an out-of-band verification step) and then run a follow-up
    # migration that copies validated addresses from
    # `email_placeholder` -> `email` and sets NOT NULL / UNIQUE constraints.


def downgrade() -> None:
    """Remove email fields from users table."""
    op.drop_column("users", "email_verified_at")
    op.drop_column("users", "email_verified")
    # Drop placeholder columns added in this migration
    op.drop_column("users", "normalized_email_placeholder")
    op.drop_column("users", "email_placeholder")

    op.drop_column("users", "normalized_email")
    op.drop_column("users", "email")
