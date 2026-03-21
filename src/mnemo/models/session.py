import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mnemo.db.database import Base


class SessionMode(str, enum.Enum):
    REVIEW = "review"
    QUIZ = "quiz"
    EXAM = "exam"


class SessionStatus(str, enum.Enum):
    ACTIVE = "active"
    ENDED = "ended"


class Session(Base):  # type: ignore[misc]
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    deck_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("decks.id", ondelete="CASCADE"), nullable=False
    )
    mode: Mapped[SessionMode] = mapped_column(
        Enum(SessionMode, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, values_callable=lambda x: [e.value for e in x]),
        default=SessionStatus.ACTIVE,
        nullable=False,
    )
    card_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    time_limit_s: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    user = relationship("User", back_populates="sessions")
    deck = relationship("Deck", back_populates="sessions")
    cards = relationship("SessionCard", back_populates="session", cascade="all, delete-orphan")
