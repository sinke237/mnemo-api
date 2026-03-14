"""
Flashcard schemas.
Per spec section 07: Flashcards.
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from mnemo.core.constants import (
    DEFAULT_DIFFICULTY,
    MAX_ANSWER_LENGTH,
    MAX_DIFFICULTY,
    MAX_QUESTION_LENGTH,
    MAX_SOURCE_REF_LENGTH,
    MAX_TAG_LENGTH,
    MIN_DIFFICULTY,
)
from mnemo.schemas.pagination import PaginationMeta


class FlashcardBase(BaseModel):
    """Shared flashcard fields."""

    question: str | None = Field(None, max_length=MAX_QUESTION_LENGTH)
    answer: str | None = Field(None, max_length=MAX_ANSWER_LENGTH)
    source_ref: str | None = Field(None, max_length=MAX_SOURCE_REF_LENGTH)
    tags: list[str] | None = Field(None)
    difficulty: int | None = Field(None, ge=MIN_DIFFICULTY, le=MAX_DIFFICULTY)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, tags: list[str] | None) -> list[str] | None:
        if tags is None:
            return tags
        for tag in tags:
            if not tag:
                raise ValueError("Tag cannot be blank")
            if len(tag) > MAX_TAG_LENGTH:
                raise ValueError(f"Tag '{tag}' exceeds {MAX_TAG_LENGTH} characters")
        return tags


class FlashcardCreate(FlashcardBase):
    """Payload for creating a flashcard."""

    question: str = Field(..., min_length=1, max_length=MAX_QUESTION_LENGTH)
    answer: str = Field(..., min_length=1, max_length=MAX_ANSWER_LENGTH)
    tags: list[str] = Field(default_factory=list)
    difficulty: int | None = Field(default=DEFAULT_DIFFICULTY, ge=MIN_DIFFICULTY, le=MAX_DIFFICULTY)


class FlashcardReplace(FlashcardBase):
    """Payload for replacing a flashcard (PUT)."""

    question: str = Field(..., min_length=1, max_length=MAX_QUESTION_LENGTH)
    answer: str = Field(..., min_length=1, max_length=MAX_ANSWER_LENGTH)


class FlashcardUpdate(FlashcardBase):
    """Payload for partial flashcard updates (PATCH)."""

    pass


class FlashcardResponse(BaseModel):
    """Flashcard response."""

    id: str
    deck_id: str
    question: str
    answer: str
    source_ref: str | None = None
    tags: list[str]
    difficulty: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FlashcardListResponse(BaseModel):
    """Paginated flashcard list response."""

    data: list[FlashcardResponse]
    pagination: PaginationMeta
