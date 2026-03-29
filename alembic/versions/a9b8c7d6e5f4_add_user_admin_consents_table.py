"""add user admin consents table

Revision ID: a9b8c7d6e5f4
Revises: 6ee6cc79f23d
Create Date: 2026-03-29 12:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a9b8c7d6e5f4"
down_revision = "6ee6cc79f23d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_admin_consents",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("user_id", sa.String(length=32), nullable=False, index=True),
        sa.Column("resource_type", sa.String(length=50), nullable=False),
        sa.Column("resource_id", sa.String(length=64), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    # Composite indexes to support common queries filtering by user and resource
    op.create_index(
        "ix_user_admin_consents_user_resource",
        "user_admin_consents",
        ["user_id", "resource_type"],
    )
    # Enforce uniqueness for consent entries where resource_id IS NOT NULL
    op.create_index(
        "uq_user_resource_consent_nonnull",
        "user_admin_consents",
        ["user_id", "resource_type", "resource_id"],
        unique=True,
        postgresql_where=sa.text("resource_id IS NOT NULL"),
    )
    # Enforce uniqueness for global (resource_id IS NULL) consents per user+resource_type
    op.create_index(
        "uq_user_resource_consent_global",
        "user_admin_consents",
        ["user_id", "resource_type"],
        unique=True,
        postgresql_where=sa.text("resource_id IS NULL"),
    )


def downgrade() -> None:
    # Drop indexes first
    op.drop_index("uq_user_resource_consent_global", table_name="user_admin_consents")
    op.drop_index("uq_user_resource_consent_nonnull", table_name="user_admin_consents")
    op.drop_index("ix_user_admin_consents_user_resource", table_name="user_admin_consents")
    op.drop_table("user_admin_consents")
