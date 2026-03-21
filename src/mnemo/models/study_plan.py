"""
StudyPlan model.
Stores generated study schedules per spec FR-07.2 and section 11.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from mnemo.db.database import Base


class StudyPlan(Base):  # type: ignore[misc]
    __tablename__ = "study_plans"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    deck_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("decks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    days: Mapped[int] = mapped_column(Integer, nullable=False)
    daily_target: Mapped[int] = mapped_column(Integer, nullable=False)
    daily_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    # JSON array of {"day": int, "date": str, "cards_to_study": int, "focus": str}
    schedule: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<StudyPlan(id={self.id}, user_id={self.user_id}, "
            f"deck_id={self.deck_id}, days={self.days})>"
        )
