"""merge heads

Revision ID: 2540a539e2b1
Revises: d4f5a6b7c8e9, e2f3a4b5c6d7, ff1e2d3c4b5a
Create Date: 2026-03-29 15:01:22.640756

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2540a539e2b1'
down_revision: Union[str, Sequence[str], None] = ('d4f5a6b7c8e9', 'e2f3a4b5c6d7', 'ff1e2d3c4b5a')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
