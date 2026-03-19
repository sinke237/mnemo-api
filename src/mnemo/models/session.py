import enum
from datetime import datetime
from uuid import UUID as PY_UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.mnemo.db.database import Base


class SessionMode(str, enum.Enum):
    REVIEW = "review"
    QUIZ = "quiz"
    EXAM = "exam"


class SessionStatus(str, enum.Enum):
    ACTIVE = "active"
    ENDED = "ended"


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[PY_UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, index=True)
    user_id: Mapped[PY_UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    deck_id: Mapped[PY_UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("decks.id"), nullable=False
    )
    mode: Mapped[SessionMode] = mapped_column(Enum(SessionMode), nullable=False)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus), default=SessionStatus.ACTIVE, nullable=False
    )
    card_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    time_limit_s: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    user = relationship("User", back_populates="sessions")
    deck = relationship("Deck", back_populates="sessions")
    cards = relationship("SessionCard", back_populates="session", cascade="all, delete-orphan")
