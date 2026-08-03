"""REST route handlers (API_SPEC.md resource groups)."""

from fastapi import APIRouter

from app.api.routers import (
    ai_generation,
    answer_options,
    auth,
    dashboard,
    health,
    join,
    live_rooms,
    media,
    participants,
    questions,
    quizzes,
    sections,
)

api_router = APIRouter()

# Public probes
api_router.include_router(health.router)

# Auth (API_SPEC.md §7)
api_router.include_router(auth.router, prefix="/admin", tags=["Auth"])

# Content management (API_SPEC.md §8–9)
api_router.include_router(quizzes.router, prefix="/quizzes", tags=["Quizzes"])
api_router.include_router(sections.router, tags=["Sections"])
api_router.include_router(questions.router, tags=["Questions"])
api_router.include_router(answer_options.router, tags=["Answer Options"])

# Media (API_SPEC.md §10)
api_router.include_router(media.router, prefix="/media", tags=["Media"])

# AI quiz generation
api_router.include_router(ai_generation.router, prefix="/ai", tags=["AI Generation"])

# Live sessions (API_SPEC.md §11–12)
api_router.include_router(live_rooms.router, prefix="/live-rooms", tags=["Live Rooms"])
api_router.include_router(join.router, prefix="/join", tags=["Join"])
api_router.include_router(participants.router, prefix="/participants", tags=["Participants"])

# Admin dashboard
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])

__all__ = ["api_router"]
