"""Add position column to session_cards

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e6f7
Create Date: 2026-03-21 06:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3c4d5e6f7a8"
down_revision: str | Sequence[str] | None = "a1b2c3d4e6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add nullable column first so we can backfill values
    op.add_column(
        "session_cards",
        sa.Column("position", sa.Integer(), nullable=True),
    )

    # Backfill positions per session ordering by created_at then id.
    # Use a temporary table and a correlated update so this is portable
    # across SQLite and Postgres (avoids UPDATE ... FROM with a CTE).
    op.execute(sa.text("""
        CREATE TEMP TABLE IF NOT EXISTS temp_session_positions AS
        SELECT id, row_number() OVER (PARTITION BY session_id ORDER BY created_at, id) - 1 AS rn
        FROM session_cards;

        UPDATE session_cards
        SET position = (
            SELECT rn FROM temp_session_positions WHERE temp_session_positions.id = session_cards.id
        )
        WHERE EXISTS (
            SELECT 1 FROM temp_session_positions WHERE temp_session_positions.id = session_cards.id
        );

        DROP TABLE IF EXISTS temp_session_positions;
    """))

    # Make column non-nullable
    op.alter_column("session_cards", "position", nullable=False)

    # Optional index to help ordering queries
    op.create_index(
        op.f("ix_session_cards_session_id_position"),
        "session_cards",
        ["session_id", "position"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_session_cards_session_id_position"), table_name="session_cards")
    op.drop_column("session_cards", "position")
