"""
v1 API router.
All v1 endpoints are registered here and mounted under /v1 in main.py.
"""

from fastapi import APIRouter

from mnemo.api.v1.routes import auth, cards, countries, decks, health, imports, users

router = APIRouter(prefix="/v1")

# Health check — no auth required
router.include_router(health.router)

# Countries — no auth required (public endpoint)
router.include_router(countries.router)

# Authentication
router.include_router(auth.router)

# Users
router.include_router(users.router)

# Future routes added here as each phase is built:
# router.include_router(sessions.router)
# router.include_router(progress.router)
router.include_router(imports.router)
router.include_router(decks.router)
router.include_router(cards.router)
