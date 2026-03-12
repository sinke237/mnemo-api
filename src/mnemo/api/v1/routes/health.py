"""
Health check endpoint.
Used by Docker, load balancers, and monitoring to verify the API is alive
and all dependencies are reachable.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from src.mnemo.db.database import check_db_connection
from src.mnemo.db.redis import check_redis_connection

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    db: str
    redis: str
    version: str


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description=(
        "Returns the health status of the API and its dependencies. "
        "Returns 200 when all systems are healthy, 503 when any dependency is down."
    ),
)
async def health_check() -> HealthResponse:
    db_ok = await check_db_connection()
    redis_ok = await check_redis_connection()

    all_ok = db_ok and redis_ok

    response = HealthResponse(
        status="ok" if all_ok else "degraded",
        db="ok" if db_ok else "unreachable",
        redis="ok" if redis_ok else "unreachable",
        version="1.0.0",
    )

    return response
