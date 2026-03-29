"""merge_heads

Revision ID: ff1e2d3c4b5a
Revises: a9b8c7d6e5f4, add_email_to_users
Create Date: 2026-03-29 12:00:00.000000

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "ff1e2d3c4b5a"
down_revision: str | Sequence[str] | None = ("a9b8c7d6e5f4", "add_email_to_users")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Merge revision to unify multiple heads."""
    pass


def downgrade() -> None:
    """Downgrade is a noop for merge revision."""
    pass
