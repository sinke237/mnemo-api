"""
Import job schemas.
Per spec section 10: CSV Import.
"""

from datetime import datetime

from pydantic import BaseModel


class ImportJobCreateResponse(BaseModel):
    """Response for POST /import/csv."""

    job_id: str
    status: str
    deck_id: str


class ImportJobStatusResponse(BaseModel):
    """Response for GET /import/{job_id}."""

    job_id: str
    status: str
    cards_imported: int
    cards_skipped: int
    errors: list[str]
    completed_at: datetime | None
    completed_at_local: str | None
