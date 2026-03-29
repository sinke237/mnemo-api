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
from alembic import op, context

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

    # Execute copy only when running online. Offline SQL generation cannot
    # execute queries; skip the copy step in that mode so SQL can be
    # generated. In online mode, perform the copy and perform a preflight
    # null-check before applying NOT NULL constraints.
    if not context.is_offline_mode():
        conn.execute(stmt)

        # Now make email fields NOT NULL and add UNIQUE constraints
        # Preflight: ensure there are no NULL email values remaining before
        # applying NOT NULL constraints. If rows remain NULL, abort with an
        # actionable error rather than letting the DB raise a less-informative
        # constraint violation.
        null_check_stmt = sa.select(sa.func.count()).select_from(users_table).where(
            sa.or_(users_table.c.email.is_(None), users_table.c.normalized_email.is_(None))
        )
        null_count = conn.execute(null_check_stmt).scalar() or 0
        if null_count:
            raise RuntimeError(
                f"Cannot make users.email/normalized_email NOT NULL: {null_count} rows have NULL values."
                " Ensure validated placeholder addresses were copied into the primary columns"
                " (see d_copy_validated_emails_to_users migration) and re-run this migration."
            )

    # Emit the NOT NULL change and unique constraints in both online and
    # offline modes. In offline mode these will be rendered into SQL; in
    # online mode they will be executed after the checks above.
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
