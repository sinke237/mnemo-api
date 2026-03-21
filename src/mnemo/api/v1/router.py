"""
v1 API router.
All v1 endpoints are registered here and mounted under /v1 in main.py.
"""

from fastapi import APIRouter

from mnemo.api.v1.routes import (
    auth,
    cards,
    countries,
    decks,
    health,
    imports,
    memory_states,
    sessions,
    users,
)

router = APIRouter(prefix="/v1")

router.include_router(health.router)
router.include_router(countries.router)
router.include_router(auth.router)
router.include_router(users.router)
router.include_router(imports.router)
router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
router.include_router(decks.router)
router.include_router(cards.router)
router.include_router(memory_states.router)
