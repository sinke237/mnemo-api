"""
Import job model.
Tracks CSV import jobs and their processing state.
Per spec section 10: CSV Import and FR-01.*.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from mnemo.db.database import Base


class ImportJob(Base):  # type: ignore[misc]
    """CSV import job table."""

    __tablename__ = "import_jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # imp_xxxxxxxx

    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    deck_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("decks.id", ondelete="CASCADE"), nullable=False, index=True
    )

    status: Mapped[str] = mapped_column(String(20), nullable=False)
    mode: Mapped[str] = mapped_column(String(10), nullable=False)

    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_text: Mapped[str] = mapped_column(Text, nullable=False)

    cards_imported: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cards_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<ImportJob(id={self.id}, deck_id={self.deck_id}, status={self.status})>"
