"""API route helpers."""

from typing import Any

from fastapi.responses import JSONResponse

from mnemo.core.constants import ErrorCode


def _error_response(
    code: ErrorCode,
    message: str,
    status_code: int,
    resource_type: str | None = None,
    resource_id: str | None = None,
    resource_name: str | None = None,
) -> JSONResponse:
    error_obj: dict[str, Any] = {
        "code": code.value,
        "message": message,
        "status": status_code,
    }
    if resource_type or resource_id or resource_name:
        resource: dict[str, Any] = {}
        if resource_type:
            resource["type"] = resource_type
        if resource_id:
            resource["id"] = resource_id
        if resource_name:
            resource["name"] = resource_name
        error_obj["resource"] = resource

    return JSONResponse(
        status_code=status_code,
        content={"error": error_obj},
    )
