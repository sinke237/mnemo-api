from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from mnemo.db.database import Base


class SessionCard(Base):  # type: ignore[misc]
    __tablename__ = "session_cards"

    id = Column(String(32), primary_key=True, index=True)
    session_id = Column(String(32), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    card_id = Column(String(32), ForeignKey("flashcards.id"), nullable=False)
    answered = Column(Boolean, default=False, nullable=False)
    position = Column(Integer, nullable=False)
    correct = Column(Boolean)
    score = Column(Integer)
    answered_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    session = relationship("Session", back_populates="cards")
    card = relationship("Flashcard")
