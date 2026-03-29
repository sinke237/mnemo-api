"""merge feature-login-reg-auth into main

Revision ID: 7ada38a5dbc7
Revises: a2b3c4d5e6f7, d1e2f3a4b5c6
Create Date: 2026-03-27 12:46:48.793693

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '7ada38a5dbc7'
down_revision: str | Sequence[str] | None = ('a2b3c4d5e6f7', 'd1e2f3a4b5c6')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
