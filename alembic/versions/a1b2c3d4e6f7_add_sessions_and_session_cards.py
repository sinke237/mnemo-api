"""Add sessions and session_cards tables

Revision ID: a1b2c3d4e6f7
Revises: f2c1b3a4d5e6
Create Date: 2026-03-21 06:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PgEnum


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e6f7"
down_revision: Union[str, Sequence[str], None] = "f2c1b3a4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enums used by sessions — DO block swallows duplicate_object so reruns are safe
    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE sessionmode AS ENUM ('review', 'quiz', 'exam');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """))
    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE sessionstatus AS ENUM ('active', 'ended');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """))

    sessionmode = PgEnum("review", "quiz", "exam", name="sessionmode", create_type=False)
    sessionstatus = PgEnum("active", "ended", name="sessionstatus", create_type=False)

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("deck_id", sa.String(length=32), nullable=False),
        sa.Column("mode", sessionmode, nullable=False),
        sa.Column("status", sessionstatus, nullable=False, server_default="active"),
        sa.Column("card_limit", sa.Integer(), nullable=True),
        sa.Column("time_limit_s", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)

    op.create_table(
        "session_cards",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("session_id", sa.String(length=32), nullable=False),
        sa.Column("card_id", sa.String(length=32), nullable=False),
        sa.Column("answered", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("correct", sa.Boolean(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("answered_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_session_cards_session_id"), "session_cards", ["session_id"], unique=False)

    # Foreign keys
    op.create_foreign_key(
        "fk_sessions_user_id_users",
        "sessions",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_sessions_deck_id_decks",
        "sessions",
        "decks",
        ["deck_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_session_cards_session_id_sessions",
        "session_cards",
        "sessions",
        ["session_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_session_cards_card_id_flashcards",
        "session_cards",
        "flashcards",
        ["card_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_session_cards_card_id_flashcards", "session_cards", type_="foreignkey")
    op.drop_constraint("fk_session_cards_session_id_sessions", "session_cards", type_="foreignkey")
    op.drop_constraint("fk_sessions_deck_id_decks", "sessions", type_="foreignkey")
    op.drop_constraint("fk_sessions_user_id_users", "sessions", type_="foreignkey")

    op.drop_index(op.f("ix_session_cards_session_id"), table_name="session_cards")
    op.drop_table("session_cards")

    op.drop_index(op.f("ix_sessions_user_id"), table_name="sessions")
    op.drop_table("sessions")

    # drop enums — DO block swallows undefined_object so reruns are safe
    op.execute(sa.text("""
        DO $$ BEGIN
            DROP TYPE sessionstatus;
        EXCEPTION WHEN undefined_object THEN NULL;
        END $$;
    """))
    op.execute(sa.text("""
        DO $$ BEGIN
            DROP TYPE sessionmode;
        EXCEPTION WHEN undefined_object THEN NULL;
        END $$;
    """))
