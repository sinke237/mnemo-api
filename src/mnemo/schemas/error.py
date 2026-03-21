"""
Error response schemas.
Standardized error format per spec section 12: Error Handling.
"""

from typing import Any

from pydantic import BaseModel, Field

from mnemo.core.constants import ErrorCode


class ErrorDetail(BaseModel):
    """
    Standard error response structure.
    All errors follow this format per NFR-05.2 and NFR-05.3.
    """

    code: ErrorCode = Field(..., description="Machine-readable error code (UPPER_SNAKE_CASE)")
    message: str = Field(..., description="Human-readable error message")
    status: int = Field(..., description="HTTP status code (mirrored in body)")
    request_id: str | None = Field(None, description="Unique trace ID for support (req_xxxxxxxx)")
    details: dict[str, Any] | None = Field(
        None, description="Additional context for validation errors"
    )
    resource: dict[str, str] | None = Field(
        None,
        description=(
            "Optional resource context, e.g. {'type': 'deck', 'id': 'dck_xxx', "
            "'name': 'My Deck'}"
        ),
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "status": 400,
                "request_id": "req_7f3a9c12",
                "details": {"name": "Field required"},
            }
        }
    }


class ErrorResponse(BaseModel):
    """Top-level error response wrapper."""

    error: ErrorDetail

    model_config = {
        "json_schema_extra": {
            "example": {
                "error": {
                    "code": "DECK_NOT_FOUND",
                    "message": "Deck not found.",
                    "status": 404,
                    "request_id": "req_7f3a9c12",
                    "resource": {"type": "deck", "id": "dck_x9y8z7w6"},
                }
            }
        }
    }
