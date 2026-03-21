from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DeckSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    deck_id: str
    name: str
    mastery_pct: float
    due_count: int


class ProgressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    total_cards: int
    mastered_cards: int
    due_today: int
    accuracy_rate: float
    study_streak_days: int
    total_sessions: int
    last_studied_at: datetime | None
    last_studied_at_local: str | None
    deck_summaries: list[DeckSummary]


class DeckProgressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    deck_id: str
    name: str
    total_cards: int
    mastered_cards: int
    mastery_pct: float
    due_count: int
    accuracy_rate: float
    total_sessions: int
    last_studied_at: datetime | None
    last_studied_at_local: str | None


class StreakResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    streak: int
    last_studied_at: datetime | None
    last_studied_at_local: str | None
