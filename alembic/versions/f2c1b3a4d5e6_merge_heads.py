"""Merge heads

Revision ID: f2c1b3a4d5e6
Revises: 8f3c2d1e4b7a, 9a1b2c3d4e5f
Create Date: 2026-03-17 00:29:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f2c1b3a4d5e6"
down_revision: Union[str, Sequence[str], None] = ("8f3c2d1e4b7a", "9a1b2c3d4e5f")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
