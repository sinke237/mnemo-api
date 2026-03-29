"""merge_heads

Revision ID: 6ee6cc79f23d
Revises: 7ada38a5dbc7, b5c6d7e8f9a0
Create Date: 2026-03-29 04:59:01.620362

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '6ee6cc79f23d'
down_revision: str | Sequence[str] | None = ('7ada38a5dbc7', 'b5c6d7e8f9a0')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
