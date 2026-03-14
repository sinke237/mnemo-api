"""API route helpers."""

from typing import cast

from fastapi import Response
from fastapi.responses import JSONResponse

from mnemo.core.constants import ErrorCode


def _error_response(code: ErrorCode, message: str, status_code: int) -> Response:
    return cast(
        Response,
        JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "code": code.value,
                    "message": message,
                    "status": status_code,
                }
            },
        ),
    )
