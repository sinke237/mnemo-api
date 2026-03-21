"""
Idempotency key model.
Stores request keys and their original responses.
Per spec NFR-03.7 and Idempotency section.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from mnemo.db.database import Base


class IdempotencyKey(Base):
    """Idempotency key table."""

    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint("user_id", "endpoint", "key", name="uq_idempotency_user_endpoint_key"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)

    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    endpoint: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(128), nullable=False)

    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<IdempotencyKey(user_id={self.user_id}, endpoint={self.endpoint})>"
