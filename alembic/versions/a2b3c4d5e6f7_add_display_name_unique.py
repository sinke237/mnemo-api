"""add_display_name_unique

Revision ID: a2b3c4d5e6f7
Revises: c0a1b2c3d4e5
Create Date: 2026-03-27 10:30:00.000000

Adds a unique constraint on users.display_name.
NULL values are permitted (multiple users may have no display_name),
because SQL UNIQUE constraints treat NULLs as distinct.
"""

from collections.abc import Sequence

from alembic import op, context
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "a2b3c4d5e6f7"
down_revision: str | None = "c0a1b2c3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Data precheck: ensure there are no duplicate non-NULL display_name values.
    # Data precheck: only run when executing online. Offline SQL generation
    # cannot perform DB queries; skip the duplicate check in that mode so
    # SQL scripts can still be generated.
    if not context.is_offline_mode():
        conn = op.get_bind()
        duplicate = conn.execute(
            text(
                """
                SELECT display_name
                FROM users
                WHERE display_name IS NOT NULL
                GROUP BY display_name
                HAVING COUNT(*) > 1
                LIMIT 1
                """
            )
        ).fetchone()
        if duplicate:
            raise Exception(
                "Cannot add unique constraint 'uq_users_display_name': "
                f"duplicate display_name '{duplicate[0]}' found. "
                "Resolve or remove duplicates before running this migration."
            )

    # Use batch_alter_table so the migration works on SQLite when render_as_batch
    # is not enabled (batch mode performs a safe ALTER by table copy).
    with op.batch_alter_table("users") as batch_op:
        batch_op.create_unique_constraint("uq_users_display_name", ["display_name"])


def downgrade() -> None:
    # Drop the unique constraint using batch_alter_table to support SQLite.
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("uq_users_display_name", type_="unique")
