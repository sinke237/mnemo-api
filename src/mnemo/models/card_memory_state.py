"""
Card memory state model.
Stores spaced repetition state per user+card.
Per spec section 05: Card Memory State.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from mnemo.core.constants import DEFAULT_EASE_FACTOR
from mnemo.db.database import Base


class CardMemoryState(Base):  # type: ignore[misc]
    """Card memory state table (composite key: card_id + user_id)."""

    __tablename__ = "card_memory_states"

    card_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("flashcards.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )

    interval_days: Mapped[float | None] = mapped_column(Float, nullable=True)
    ease_factor: Mapped[float] = mapped_column(Float, nullable=False, default=DEFAULT_EASE_FACTOR)
    repetitions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<CardMemoryState(card_id={self.card_id}, user_id={self.user_id})>"
