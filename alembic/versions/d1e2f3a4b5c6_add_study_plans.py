"""Add study_plans table

Revision ID: d1e2f3a4b5c6
Revises: b3c4d5e6f7a8
Create Date: 2026-03-21 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: str | Sequence[str] | None = "b3c4d5e6f7a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "study_plans",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("deck_id", sa.String(length=32), nullable=False),
        sa.Column("goal", sa.Text(), nullable=True),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column("daily_target", sa.Integer(), nullable=False),
        sa.Column("daily_minutes", sa.Integer(), nullable=False),
        sa.Column("schedule", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_study_plans_user_id"), "study_plans", ["user_id"], unique=False)
    op.create_index(op.f("ix_study_plans_deck_id"), "study_plans", ["deck_id"], unique=False)

    op.create_foreign_key(
        "fk_study_plans_user_id_users",
        "study_plans",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_study_plans_deck_id_decks",
        "study_plans",
        "decks",
        ["deck_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_study_plans_deck_id_decks", "study_plans", type_="foreignkey")
    op.drop_constraint("fk_study_plans_user_id_users", "study_plans", type_="foreignkey")
    op.drop_index(op.f("ix_study_plans_deck_id"), table_name="study_plans")
    op.drop_index(op.f("ix_study_plans_user_id"), table_name="study_plans")
    op.drop_table("study_plans")
