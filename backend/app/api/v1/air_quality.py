from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_app_settings, get_response_meta
from app.core.config import Settings
from app.db.session import get_db_session
from app.schemas.air_quality import (
    AirQualityForecastSchema,
    CurrentAirQualitySchema,
    HistoricalAirQualitySchema,
    HistoryPeriodLiteral,
    MonitoringStationSchema,
    StationGeoJsonCollectionSchema,
)
from app.schemas.common import ApiResponse, ResponseMeta
from app.services.air_quality.aqi_calculator import AQIStandard
from app.services.air_quality.telemetry_service import AirQualityTelemetryService

router = APIRouter(prefix="/air-quality", tags=["air-quality"])


@router.get("/current", response_model=ApiResponse[CurrentAirQualitySchema])
async def get_current_air_quality(
    city: Annotated[
        str,
        Query(min_length=2, max_length=100, description="City name (e.g., Delhi, Bengaluru)"),
    ],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
    standard: Annotated[AQIStandard, Query()] = AQIStandard.INDIA_NAQI,
) -> ApiResponse[CurrentAirQualitySchema]:
    service = AirQualityTelemetryService(session=db, settings=settings)
    data = await service.get_current_air_quality(city=city, standard=standard)
    return ApiResponse(data=data, meta=meta)


@router.get("/history", response_model=ApiResponse[HistoricalAirQualitySchema])
async def get_historical_air_quality(
    city: Annotated[str, Query(min_length=2, max_length=100)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
    period: Annotated[HistoryPeriodLiteral, Query()] = "24h",
    standard: Annotated[AQIStandard, Query()] = AQIStandard.INDIA_NAQI,
) -> ApiResponse[HistoricalAirQualitySchema]:
    service = AirQualityTelemetryService(session=db, settings=settings)
    data = await service.get_historical_air_quality(
        city=city, standard=standard, period=period
    )
    return ApiResponse(data=data, meta=meta)


@router.get("/forecast", response_model=ApiResponse[AirQualityForecastSchema])
async def get_air_quality_forecast(
    city: Annotated[str, Query(min_length=2, max_length=100)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
    hours: Annotated[int, Query(ge=6, le=72)] = 24,
    standard: Annotated[AQIStandard, Query()] = AQIStandard.INDIA_NAQI,
) -> ApiResponse[AirQualityForecastSchema]:
    service = AirQualityTelemetryService(session=db, settings=settings)
    data = await service.get_air_quality_forecast(
        city=city, standard=standard, hours=hours
    )
    return ApiResponse(data=data, meta=meta)


@router.get("/stations", response_model=ApiResponse[list[MonitoringStationSchema]])
async def get_nearby_air_quality_stations(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
    city: Annotated[str | None, Query(min_length=2, max_length=100)] = None,
    lat: Annotated[float | None, Query(ge=-90.0, le=90.0)] = None,
    lon: Annotated[float | None, Query(ge=-180.0, le=180.0)] = None,
    radius_km: Annotated[float, Query(ge=1.0, le=100.0)] = 25.0,
    standard: Annotated[AQIStandard, Query()] = AQIStandard.INDIA_NAQI,
) -> ApiResponse[list[MonitoringStationSchema]]:
    service = AirQualityTelemetryService(session=db, settings=settings)
    stations = await service.get_nearby_stations(
        standard=standard,
        city=city,
        latitude=lat,
        longitude=lon,
        radius_km=radius_km,
    )
    return ApiResponse(data=stations, meta=meta)


@router.get("/map", response_model=ApiResponse[StationGeoJsonCollectionSchema])
async def get_air_quality_map_geojson(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
    bbox: Annotated[
        str | None,
        Query(description="Bounding box: minLon,minLat,maxLon,maxLat"),
    ] = None,
    city: Annotated[str | None, Query(min_length=2, max_length=100)] = None,
    standard: Annotated[AQIStandard, Query()] = AQIStandard.INDIA_NAQI,
) -> ApiResponse[StationGeoJsonCollectionSchema]:
    service = AirQualityTelemetryService(session=db, settings=settings)
    geojson = await service.get_stations_geojson(
        standard=standard, bbox=bbox, city=city
    )
    return ApiResponse(data=geojson, meta=meta)
