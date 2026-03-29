"""
User model.
Stores user profile data including email, country, timezone, and learning preferences.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from mnemo.core.constants import DEFAULT_DAILY_GOAL_CARDS
from mnemo.db.database import Base

if TYPE_CHECKING:
    from mnemo.models.session import Session


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('user','admin')", name="valid_role"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)

    # Authentication fields
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    normalized_email: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    email_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Profile fields
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    normalized_display_name: Mapped[str | None] = mapped_column(
        String(100), nullable=True, unique=True
    )

    # Location and preferences
    country: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    locale: Mapped[str | None] = mapped_column(String(10), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    education_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    preferred_language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    daily_goal_cards: Mapped[int] = mapped_column(
        Integer, nullable=False, default=DEFAULT_DAILY_GOAL_CARDS
    )

    # Role and permissions
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="user", server_default="user"
    )
    admin_access_granted: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )
    admin_access_granted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    sessions: Mapped[list["Session"]] = relationship(
        "Session", back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def token_scopes(self) -> list[str]:
        """Transient per-request scopes; populated by the auth dependency."""
        scopes: list[str] = self.__dict__.get("_token_scopes", [])
        return list(scopes)

    @token_scopes.setter
    def token_scopes(self, value: list[str]) -> None:
        self.__dict__["_token_scopes"] = list(value)

    def __repr__(self) -> str:
        # Avoid exposing full email (PII) in logs/representations.
        # Keep a short prefix (1-2 chars) and replace the rest with a fixed mask.
        if self.email:
            prefix = self.email[:2] if len(self.email) >= 2 else self.email[:1]
            masked_email = f"{prefix}***"
        else:
            masked_email = None
        return f"<User(id={self.id}, email={masked_email}, role={self.role})>"
