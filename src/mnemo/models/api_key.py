"""
API Key model.
Stores hashed API keys with permission scopes.
Per spec section 02: Authentication and NFR-03.2.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from mnemo.db.database import Base


class APIKey(Base):  # type: ignore[misc]
    """
    API Key table.

    SECURITY (per spec NFR-03.2):
    - API keys are NEVER stored in plaintext
    - key_hash stores the bcrypt hash of the full key (mnm_live_xxx)
    - The plain key is shown ONLY ONCE at creation time
    - key_prefix stores the prefix (mnm_live_ or mnm_test_) for identification
    """

    __tablename__ = "api_keys"

    # Primary key
    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # Generated ID

    # User reference
    user_id: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )  # References users.id

    # Key data (hashed per NFR-03.2)
    key_hash: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True, index=True
    )  # bcrypt hash
    key_prefix: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # mnm_live_ or mnm_test_
    key_hint: Mapped[str] = mapped_column(String(8), nullable=False)  # Last 4 chars for UI display

    # Metadata
    name: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # e.g., "Production API Key"
    is_live: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)

    # Permission scopes (stored as JSON array in TEXT field)
    # e.g., '["decks:read", "decks:write", "sessions:run"]'
    scopes: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON array as string

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<APIKey(id={self.id}, prefix={self.key_prefix}, active={self.is_active})>"
