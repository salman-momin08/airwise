from __future__ import annotations

from fastapi import APIRouter

from app.core.exceptions import ExternalProviderUnavailableError

router = APIRouter(prefix="/weather", tags=["weather"])


@router.get("/current")
async def get_current_weather(city: str) -> dict[str, object]:
    raise ExternalProviderUnavailableError(
        code="WEATHER_PROVIDER_NOT_CONFIGURED",
        message=f"Live weather telemetry for '{city}' requires Phase 3 WEATHER_API_KEY onboarding.",
    )
