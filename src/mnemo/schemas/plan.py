"""
Study plan schemas.
Request/response models for POST /users/{id}/plan and GET /users/{id}/plan.
Per spec FR-07.2 and section 11.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ScheduleDay(BaseModel):
    """A single day entry in a study schedule."""

    model_config = ConfigDict(from_attributes=True)

    day: int
    date: str  # YYYY-MM-DD in user's local timezone (FR-07.2)
    cards_to_study: int
    focus: str


class PlanCreate(BaseModel):
    """Request body for POST /users/{id}/plan."""

    deck_id: str
    goal: str | None = None
    days: int = Field(..., ge=1, le=365, description="Days available. Min: 1, max: 365.")
    daily_minutes: int = Field(default=30, ge=1, description="Minutes available per day.")


class PlanResponse(BaseModel):
    """Response body for study plan endpoints."""

    model_config = ConfigDict(from_attributes=True)

    plan_id: str
    deck_id: str
    goal: str | None
    days: int
    daily_target: int
    daily_minutes: int
    schedule: list[ScheduleDay]
    created_at: datetime
