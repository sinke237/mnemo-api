from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from src.mnemo.models.session import SessionMode, SessionStatus
from src.mnemo.schemas.flashcard import FlashcardBase as Flashcard


class SessionStart(BaseModel):
    deck_id: UUID
    mode: SessionMode = SessionMode.REVIEW
    card_limit: int | None = Field(None, ge=1, le=100)
    due_only: bool = False
    focus_weak: bool = False
    time_limit_s: int | None = Field(None, ge=60)


class Session(BaseModel):
    session_id: UUID
    status: SessionStatus
    cards_total: int
    cards_done: int
    current_card: Flashcard | None
    expires_at: datetime
    expires_at_local: str

    class Config:
        orm_mode = True


class Answer(BaseModel):
    answer: str = Field(..., max_length=2000)
    time_taken_s: int | None
    confidence: int | None = Field(None, ge=1, le=3)


class AnswerResult(BaseModel):
    score: int
    is_correct: bool
    canonical_answer: str
    feedback: str
    next_card: Flashcard | None
    session_progress: dict[str, int]


class SessionSummary(BaseModel):
    session_id: UUID
    deck_id: UUID
    mode: SessionMode
    status: SessionStatus
    started_at: datetime
    ended_at: datetime
    total_cards: int
    cards_answered: int
    correct_answers: int
    accuracy: float
    time_taken_s: int
