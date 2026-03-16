"""Add decks, flashcards, card memory states, and idempotency keys

Revision ID: 6f9b2c1a7d4e
Revises: 4c8d2b1e3f7
Create Date: 2026-03-14 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6f9b2c1a7d4e"
down_revision: Union[str, Sequence[str], None] = "4c8d2b1e3f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "decks",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("card_count", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("source_file", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_decks_user_name"),
    )
    op.create_index(op.f("ix_decks_user_id"), "decks", ["user_id"], unique=False)

    op.create_table(
        "flashcards",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("deck_id", sa.String(length=32), nullable=False),
        sa.Column("question", sa.String(length=1000), nullable=False),
        sa.Column("answer", sa.String(length=2000), nullable=False),
        sa.Column("source_ref", sa.String(length=255), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("difficulty", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_flashcards_deck_id"), "flashcards", ["deck_id"], unique=False)

    op.create_table(
        "card_memory_states",
        sa.Column("card_id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("interval_days", sa.Float(), nullable=True),
        sa.Column("ease_factor", sa.Float(), nullable=False),
        sa.Column("repetitions", sa.Integer(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_score", sa.Integer(), nullable=True),
        sa.Column("streak", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("card_id", "user_id"),
    )

    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("endpoint", sa.String(length=200), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("response_body", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "endpoint", "key", name="uq_idempotency_user_endpoint_key"
        ),
    )
    op.create_index(
        op.f("ix_idempotency_keys_endpoint"),
        "idempotency_keys",
        ["endpoint"],
        unique=False,
    )
    op.create_index(
        op.f("ix_idempotency_keys_user_id"),
        "idempotency_keys",
        ["user_id"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_decks_user_id_users",
        "decks",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_flashcards_deck_id_decks",
        "flashcards",
        "decks",
        ["deck_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_card_memory_states_card_id_flashcards",
        "card_memory_states",
        "flashcards",
        ["card_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_card_memory_states_user_id_users",
        "card_memory_states",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_idempotency_keys_user_id_users",
        "idempotency_keys",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_idempotency_keys_user_id_users", "idempotency_keys", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_card_memory_states_user_id_users", "card_memory_states", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_card_memory_states_card_id_flashcards",
        "card_memory_states",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_flashcards_deck_id_decks", "flashcards", type_="foreignkey"
    )
    op.drop_constraint("fk_decks_user_id_users", "decks", type_="foreignkey")

    op.drop_index(op.f("ix_idempotency_keys_user_id"), table_name="idempotency_keys")
    op.drop_index(op.f("ix_idempotency_keys_endpoint"), table_name="idempotency_keys")
    op.drop_table("idempotency_keys")

    op.drop_table("card_memory_states")

    op.drop_index(op.f("ix_flashcards_deck_id"), table_name="flashcards")
    op.drop_table("flashcards")

    op.drop_index(op.f("ix_decks_user_id"), table_name="decks")
    op.drop_table("decks")
