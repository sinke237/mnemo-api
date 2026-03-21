from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DeckProgressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    deck_id: str
    total_answered: int
    correct_answers: int
    accuracy: float
    last_studied_at: datetime | None
    last_studied_at_local: str | None


class ProgressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_answered: int
    correct_answers: int
    accuracy: float
    last_studied_at: datetime | None
    last_studied_at_local: str | None


class StreakResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    streak: int
    last_studied_at: datetime | None
    last_studied_at_local: str | None
