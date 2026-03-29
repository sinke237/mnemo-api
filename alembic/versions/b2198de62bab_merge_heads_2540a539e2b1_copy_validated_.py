"""Merge heads 2540a539e2b1 + copy_validated_emails

Revision ID: b2198de62bab
Revises: 2540a539e2b1, copy_validated_emails
Create Date: 2026-03-29 15:59:08.025397

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = 'b2198de62bab'
down_revision: str | Sequence[str] | None = ('2540a539e2b1', 'copy_validated_emails')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
