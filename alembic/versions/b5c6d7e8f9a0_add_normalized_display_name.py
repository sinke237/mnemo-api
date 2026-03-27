"""add_normalized_display_name

Revision ID: b5c6d7e8f9a0
Revises: a2b3c4d5e6f7
Create Date: 2026-03-27 10:45:00.000000

Add a normalized_display_name column and unique constraint to users.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "b5c6d7e8f9a0"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add nullable column first
    op.add_column(
        "users",
        sa.Column("normalized_display_name", sa.String(length=100), nullable=True),
    )

    conn = op.get_bind()
    # Backfill normalized values in batches to avoid long table locks and
    # transaction log growth. Process rows where `normalized_display_name` is
    # NULL in small batches and commit between batches.
    batch_size = 100
    while True:
        rows = conn.execute(
            text(
                "SELECT id "
                "FROM users "
                "WHERE normalized_display_name IS NULL AND display_name IS NOT NULL "
                "LIMIT :limit"
            ),
            {"limit": batch_size},
        ).fetchall()
        if not rows:
            break
        ids = [r[0] for r in rows]
        # Build a parametrized IN-clause to update only these rows
        params = {f"id_{i}": id_ for i, id_ in enumerate(ids)}
        placeholders = ", ".join(f":id_{i}" for i in range(len(ids)))
        update_sql = text(
            f"UPDATE users SET normalized_display_name = lower(trim(display_name)) WHERE id IN ({placeholders})"
        )
        conn.execute(update_sql, params)
        # Attempt to commit so each batch runs in its own transaction; some
        # migration environments provide a Connection with commit(). If not,
        # ignore and continue.
        try:
            conn.commit()
        except Exception:
            pass

    # Ensure there are no duplicates in the normalized column before adding unique constraint
    dup_count = conn.execute(
        text(
            "SELECT COUNT(*) FROM ("
            "SELECT normalized_display_name FROM users "
            "WHERE normalized_display_name IS NOT NULL "
            "GROUP BY normalized_display_name HAVING COUNT(*) > 1) AS t"
        )
    ).scalar()
    if dup_count and int(dup_count) > 0:
        raise Exception(
            "Cannot add unique constraint 'uq_users_normalized_display_name': duplicate normalized display_name(s) found. "
            f"Resolve duplicates before running this migration (duplicate groups: {int(dup_count)})."
        )

    # Add unique constraint using batch_alter_table to support SQLite
    with op.batch_alter_table("users") as batch_op:
        batch_op.create_unique_constraint("uq_users_normalized_display_name", ["normalized_display_name"])


def downgrade() -> None:
    # Drop the unique constraint and remove the column
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("uq_users_normalized_display_name", type_="unique")

    op.drop_column("users", "normalized_display_name")
