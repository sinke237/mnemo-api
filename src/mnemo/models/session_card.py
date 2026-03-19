from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.mnemo.db.database import Base


class SessionCard(Base):
    __tablename__ = "session_cards"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    card_id = Column(UUID(as_uuid=True), ForeignKey("flashcards.id"), nullable=False)
    answered = Column(Boolean, default=False, nullable=False)
    correct = Column(Boolean)
    score = Column(Integer)
    answered_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    session = relationship("Session", back_populates="cards")
    card = relationship("Flashcard")
