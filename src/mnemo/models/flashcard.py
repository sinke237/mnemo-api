"""
Flashcard model.
Stores individual question-answer pairs.
Per spec section 07: Flashcards.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from mnemo.core.constants import DEFAULT_DIFFICULTY
from mnemo.db.database import Base


class Flashcard(Base):  # type: ignore[misc]
    """Flashcard table."""

    __tablename__ = "flashcards"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # crd_xxxxxxxx

    deck_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("decks.id", ondelete="CASCADE"), nullable=False, index=True
    )

    question: Mapped[str] = mapped_column(String(1000), nullable=False)
    answer: Mapped[str] = mapped_column(String(2000), nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False, default=DEFAULT_DIFFICULTY)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    deck = relationship("Deck", back_populates="cards")
    memory_states = relationship(
        "CardMemoryState", back_populates="card", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Flashcard(id={self.id}, deck_id={self.deck_id})>"
