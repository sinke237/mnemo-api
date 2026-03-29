"""
User admin consent model.
Records when a user grants admin access for a specific resource type or resource id.
"""

from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from mnemo.db.database import Base


class UserAdminConsent(Base):
    __tablename__ = "user_admin_consents"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "resource_type", "resource_id", name="uq_user_resource_consent"
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return (
            f"<UserAdminConsent(id={self.id}, user_id={self.user_id}, "
            f"resource_type={self.resource_type}, resource_id={self.resource_id})>"
        )
