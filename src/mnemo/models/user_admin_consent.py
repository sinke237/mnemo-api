"""
User admin consent model.
Records when a user grants admin access for a specific resource type or resource id.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mnemo.db.database import Base

if TYPE_CHECKING:
    from mnemo.models.user import User


class UserAdminConsent(Base):
    __tablename__ = "user_admin_consents"
    # Enforce uniqueness for resource-specific consents (user_id, resource_type, resource_id)
    # and a separate partial unique index for global consents where resource_id IS NULL
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "resource_type",
            "resource_id",
            name="uq_user_admin_consents_user_resource_resourceid",
        ),
        Index(
            "uq_user_admin_consents_global",
            "user_id",
            "resource_type",
            unique=True,
            postgresql_where=text("resource_id IS NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ORM relationship to the owning User (allows navigating consent.user)
    user: Mapped["User"] = relationship("User", back_populates="consents")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return (
            f"<UserAdminConsent(id={self.id}, user_id={self.user_id}, "
            f"resource_type={self.resource_type}, resource_id={self.resource_id})>"
        )
