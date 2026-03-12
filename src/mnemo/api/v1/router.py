"""
v1 API router.
All v1 endpoints are registered here and mounted under /v1 in main.py.
"""

from fastapi import APIRouter

from src.mnemo.api.v1.routes import health

router = APIRouter(prefix="/v1")

# Health check — no auth required
router.include_router(health.router)

# Future routes added here as each phase is built:
# router.include_router(auth.router)
# router.include_router(users.router)
# router.include_router(decks.router)
# router.include_router(cards.router)
# router.include_router(sessions.router)
# router.include_router(progress.router)
# router.include_router(imports.router)
