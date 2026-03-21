"""Add key_lookup column to api_keys for indexed lookups

Revision ID: 3b9f1c2a5d6
Revises: e163c3063cf1
Create Date: 2026-03-13 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '3b9f1c2a5d6'
down_revision = 'e163c3063cf1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add a short lookup fragment to speed up API key validation queries
    op.add_column('api_keys', sa.Column('key_lookup', sa.String(length=16), nullable=True))
    op.create_index(op.f('ix_api_keys_key_lookup'), 'api_keys', ['key_lookup'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_api_keys_key_lookup'), table_name='api_keys')
    op.drop_column('api_keys', 'key_lookup')
