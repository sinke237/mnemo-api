"""
Pydantic schemas for card memory states.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CardMemoryStateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    card_id: str
    user_id: str
    interval_days: float | None
    ease_factor: float
    repetitions: int
    due_at: datetime | None
    due_at_local: str | None = None
    last_score: int | None
    streak: int


class DueCardResponse(BaseModel):
    id: str
    deck_id: str
    question: str
    due_at: datetime
    due_at_local: str | None
    overdue_by: str | None
    overdue_by_seconds: int | None
    ease_factor: float


class DueCardListResponse(BaseModel):
    due_count: int
    cards: list[DueCardResponse]


class WeakSpotResponse(BaseModel):
    id: str
    deck_id: str
    question: str
    ease_factor: float
    last_score: int | None
    repetitions: int


class WeakSpotListResponse(BaseModel):
    count: int
    cards: list[WeakSpotResponse]


class AnswerRequest(BaseModel):
    score: int = Field(..., ge=0, le=5)
