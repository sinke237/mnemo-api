"""
Password reset token model.
Stores hashed reset tokens linked to user accounts.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from mnemo.db.database import Base


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)

    # Store only a hash of the token for security
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user = relationship("User", passive_deletes=True)

    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Optional metadata
    ip_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Optional request id for tracing the originating request that created this token
    request_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=False)

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<PasswordResetToken(id={self.id}, user_id={self.user_id})>"
