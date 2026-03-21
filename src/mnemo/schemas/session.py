from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from mnemo.models.session import SessionMode, SessionStatus


class FlashcardInSession(BaseModel):
    """Flashcard representation inside a session response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    deck_id: str
    question: str | None = None
    answer: str | None = None
    source_ref: str | None = None
    tags: list[str] | None = None
    difficulty: int | None = None


class SessionStart(BaseModel):
    deck_id: str
    mode: SessionMode = SessionMode.REVIEW
    card_limit: int | None = Field(None, ge=1, le=100)
    due_only: bool = False
    focus_weak: bool = False
    time_limit_s: int | None = Field(None, ge=60)


class Session(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: str
    status: SessionStatus
    cards_total: int
    cards_done: int
    current_card: FlashcardInSession | None
    expires_at: datetime
    expires_at_local: str


class Answer(BaseModel):
    answer: str = Field(..., max_length=2000)
    time_taken_s: int | None = None
    confidence: int | None = Field(None, ge=1, le=3)


class AnswerResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    score: int
    is_correct: bool
    canonical_answer: str
    feedback: str
    next_card: FlashcardInSession | None
    session_progress: dict[str, int]


class SessionSummary(BaseModel):
    session_id: str
    deck_id: str
    mode: SessionMode
    status: SessionStatus
    started_at: datetime
    ended_at: datetime | None
    total_cards: int
    cards_answered: int
    correct_answers: int
    accuracy: float
    time_taken_s: int
