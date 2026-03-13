"""Alter api_keys.id column length to varchar(40)

Revision ID: 4c8d2b1e3f7
Revises: 3b9f1c2a5d6
Create Date: 2026-03-13 07:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '4c8d2b1e3f7'
down_revision = '3b9f1c2a5d6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Increase api_keys.id column length to accommodate UUID4-based IDs
    op.alter_column('api_keys', 'id',
                    existing_type=sa.String(length=32),
                    type_=sa.String(length=40),
                    existing_nullable=False)


def downgrade() -> None:
    # Revert to original length (will fail if any IDs exceed 32 chars)
    op.alter_column('api_keys', 'id',
                    existing_type=sa.String(length=40),
                    type_=sa.String(length=32),
                    existing_nullable=False)
