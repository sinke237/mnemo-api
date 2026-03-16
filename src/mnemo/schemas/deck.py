"""
Deck schemas.
Per spec section 06: Decks.
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from mnemo.core.constants import MAX_DECK_NAME_LENGTH, MAX_TAG_LENGTH
from mnemo.schemas.pagination import PaginationMeta


class DeckBase(BaseModel):
    """Shared deck fields."""

    name: str | None = Field(None, max_length=MAX_DECK_NAME_LENGTH)
    description: str | None = Field(None)
    tags: list[str] | None = Field(None)

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


class DeckCreate(DeckBase):
    """Payload for creating a deck."""

    name: str = Field(..., min_length=1, max_length=MAX_DECK_NAME_LENGTH)
    description: str | None = None
    tags: list[str] = Field(default_factory=list)


class DeckReplace(DeckBase):
    """Payload for replacing deck metadata (PUT)."""

    name: str = Field(..., min_length=1, max_length=MAX_DECK_NAME_LENGTH)


class DeckUpdate(DeckBase):
    """Payload for partial deck updates (PATCH)."""

    pass


class DeckResponse(BaseModel):
    """Full deck response."""

    id: str
    name: str
    description: str | None = None
    tags: list[str]
    card_count: int
    version: int
    created_at: datetime
    updated_at: datetime
    source_file: str | None = None

    model_config = {"from_attributes": True}


class DeckListItem(BaseModel):
    """Deck list item response."""

    id: str
    name: str
    card_count: int
    tags: list[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DeckListResponse(BaseModel):
    """Paginated deck list response."""

    data: list[DeckListItem]
    pagination: PaginationMeta
