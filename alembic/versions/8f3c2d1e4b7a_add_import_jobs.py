"""Add import jobs table

Revision ID: 8f3c2d1e4b7a
Revises: 7b2a1d4e9f0c
Create Date: 2026-03-16 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8f3c2d1e4b7a"
down_revision: str | Sequence[str] | None = "7b2a1d4e9f0c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "import_jobs",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("deck_id", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("mode", sa.String(length=10), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("file_text", sa.Text(), nullable=False),
        sa.Column("cards_imported", sa.Integer(), nullable=False),
        sa.Column("cards_skipped", sa.Integer(), nullable=False),
        sa.Column("errors", sa.JSON(), nullable=False),
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
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_import_jobs_user_id"), "import_jobs", ["user_id"], unique=False)
    op.create_index(op.f("ix_import_jobs_deck_id"), "import_jobs", ["deck_id"], unique=False)

    op.create_foreign_key(
        "fk_import_jobs_user_id_users",
        "import_jobs",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_import_jobs_deck_id_decks",
        "import_jobs",
        "decks",
        ["deck_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_import_jobs_deck_id_decks", "import_jobs", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_import_jobs_user_id_users", "import_jobs", type_="foreignkey"
    )

    op.drop_index(op.f("ix_import_jobs_deck_id"), table_name="import_jobs")
    op.drop_index(op.f("ix_import_jobs_user_id"), table_name="import_jobs")
    op.drop_table("import_jobs")
