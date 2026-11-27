from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_app_settings, get_response_meta
from app.core.config import Settings
from app.db.session import get_db_session
from app.schemas.common import ApiResponse, ResponseMeta
from app.schemas.weather import CurrentWeatherSchema
from app.services.weather.weather_service import WeatherTelemetryService

router = APIRouter(prefix="/weather", tags=["weather"])

@router.get("/current", response_model=ApiResponse[CurrentWeatherSchema])
async def get_current_weather(
    city: Annotated[str, Query(min_length=2, max_length=100)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
) -> ApiResponse[CurrentWeatherSchema]:
    service = WeatherTelemetryService(session=db, settings=settings)
    data = await service.get_current_weather(city=city)
    return ApiResponse(data=data, meta=meta)
