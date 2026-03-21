"""
User model.
Stores user profile data including country, timezone, and learning preferences.
Per spec section 11: User Profiles and FR-07.1.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from mnemo.core.constants import DEFAULT_DAILY_GOAL_CARDS
from mnemo.db.database import Base

if TYPE_CHECKING:
    from mnemo.models.session import Session


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    locale: Mapped[str | None] = mapped_column(String(10), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    education_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    preferred_language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    daily_goal_cards: Mapped[int] = mapped_column(
        Integer, nullable=False, default=DEFAULT_DAILY_GOAL_CARDS
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    sessions: Mapped[list["Session"]] = relationship(
        "Session", back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def token_scopes(self) -> list[str]:
        """Transient per-request scopes; populated by the auth dependency."""
        scopes: list[str] = self.__dict__.get("_token_scopes", [])
        return scopes

    @token_scopes.setter
    def token_scopes(self, value: list[str]) -> None:
        self.__dict__["_token_scopes"] = value

    def __repr__(self) -> str:
        return f"<User(id={self.id}, country={self.country}, timezone={self.timezone})>"
