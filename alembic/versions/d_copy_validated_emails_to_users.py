"""Copy validated placeholder emails into primary email fields and apply constraints

Revision ID: copy_validated_emails
Revises: add_email_to_users
Create Date: 2026-03-29 12:30:00.000000

This migration should be run after operators have validated addresses collected
into `email_placeholder` (for example via a confirmation flow or manual review)
and marked `email_verified` for those rows. The migration copies validated
placeholders into `email`, sets normalized values, makes `email` NOT NULL,
and adds UNIQUE constraints on `email`/`normalized_email`.

NOTE: Only rows where `email` IS NULL and `email_placeholder` IS NOT NULL and
`email_verified` = TRUE are copied. Operators should ensure `email_verified`
accurately reflects verified addresses before applying this migration.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "copy_validated_emails"
down_revision: str | Sequence[str] | None = "add_email_to_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Copy validated placeholder emails to primary columns and add constraints."""
    conn = op.get_bind()
    users_table = sa.table(
        "users",
        sa.column("id", sa.String),
        sa.column("email", sa.String),
        sa.column("normalized_email", sa.String),
        sa.column("email_placeholder", sa.String),
        sa.column("normalized_email_placeholder", sa.String),
        sa.column("email_verified", sa.Boolean),
    )

    # Copy only when primary email is missing, placeholder is present and verified is True
    stmt = (
        sa.update(users_table)
        .where(
            sa.and_(
                users_table.c.email.is_(None),
                users_table.c.email_placeholder.isnot(None),
                users_table.c.email_verified == sa.true(),
            )
        )
        .values(
            email=users_table.c.email_placeholder,
            normalized_email=sa.func.lower(users_table.c.email_placeholder),
        )
    )

    conn.execute(stmt)

    # Now make email fields NOT NULL and add UNIQUE constraints
    op.alter_column("users", "email", nullable=False)
    op.alter_column("users", "normalized_email", nullable=False)

    op.create_unique_constraint("uq_users_email", "users", ["email"])
    op.create_unique_constraint("uq_users_normalized_email", "users", ["normalized_email"])

    # Optional: remove placeholder columns if no longer needed. Keep by default to allow
    # audit/rollback; operators may drop them manually in a later migration.


def downgrade() -> None:
    """Revert constraint changes; do not attempt to repopulate placeholders."""
    op.drop_constraint("uq_users_normalized_email", "users", type_="unique")
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.alter_column("users", "normalized_email", nullable=True)
    op.alter_column("users", "email", nullable=True)
