"""
User model.
Stores user profile data including country, timezone, and learning preferences.
Per spec section 11: User Profiles and FR-07.1.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from mnemo.core.constants import DEFAULT_DAILY_GOAL_CARDS
from mnemo.db.database import Base


class User(Base):  # type: ignore[misc]
    """
    User profile table.

    TIMEZONE POLICY (per spec):
    - country is REQUIRED and is the sole source of timezone resolution
    - timezone is derived from country (never auto-detected from device)
    - For multi-timezone countries, user selects specific timezone after country selection
    """

    __tablename__ = "users"

    # Primary key
    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # usr_xxxxxxxx

    # Profile fields
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Location & timezone (FR-07.1)
    country: Mapped[str] = mapped_column(
        String(2), nullable=False, index=True
    )  # ISO 3166-1 alpha-2
    locale: Mapped[str | None] = mapped_column(String(10), nullable=True)  # BCP 47 (e.g., fr-CM)
    timezone: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # IANA timezone (Africa/Douala)

    # Learning preferences
    education_level: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # EducationLevel enum
    preferred_language: Mapped[str] = mapped_column(
        String(10), nullable=False, default="en"
    )  # BCP 47 language
    daily_goal_cards: Mapped[int] = mapped_column(
        Integer, nullable=False, default=DEFAULT_DAILY_GOAL_CARDS
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, country={self.country}, timezone={self.timezone})>"
