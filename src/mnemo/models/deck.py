"""
Deck model.
Stores deck metadata and card counts.
Per spec section 06: Decks and FR-02.*.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from mnemo.db.database import Base

if TYPE_CHECKING:
    from mnemo.models.session import Session


class Deck(Base):
    __tablename__ = "decks"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_decks_user_name"),
        Index("ix_decks_user_name_lower", "user_id", text("lower(name)"), unique=True),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    card_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source_file: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    cards = relationship(
        "Flashcard",
        back_populates="deck",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    sessions: Mapped[list["Session"]] = relationship(
        "Session", back_populates="deck", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Deck(id={self.id}, user_id={self.user_id}, name={self.name})>"
