"""Top-level `/api/v1` API router aggregating all bounded-context sub-routers."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    air_quality,
    alerts,
    assistant,
    auth,
    community,
    impact,
    locations,
    recommendations,
    routines,
    system_cron,
    users,
    weather,
)

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth.router)
api_v1_router.include_router(users.router)
api_v1_router.include_router(locations.router)
api_v1_router.include_router(air_quality.router)
api_v1_router.include_router(weather.router)
api_v1_router.include_router(assistant.router)
api_v1_router.include_router(recommendations.router)
api_v1_router.include_router(routines.router)
api_v1_router.include_router(impact.router)
api_v1_router.include_router(alerts.router)
api_v1_router.include_router(alerts.notifications_router)
api_v1_router.include_router(community.router)
api_v1_router.include_router(admin.router)
api_v1_router.include_router(system_cron.router)
