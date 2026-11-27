"""Air quality telemetry service coordinating cache, primary/fallback providers, and DB storage."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import AirWiseError, ExternalProviderUnavailableError
from app.integrations.air_quality.provider import (
    CITY_COORDINATE_GAZETTEER,
    FailoverAirQualityClient,
    NormalizedStationTelemetry,
    is_timestamp_stale,
    lookup_city_centroid,
    resolve_air_quality_adapter,
)
from app.repositories.telemetry_repository import TelemetryRepository, haversine_distance_km
from app.schemas.air_quality import (
    AirQualityForecastSchema,
    CurrentAirQualitySchema,
    ForecastPointSchema,
    GeoJsonPointGeometrySchema,
    HistoricalAirQualityPointSchema,
    HistoricalAirQualitySchema,
    HistoryPeriodLiteral,
    MonitoringStationSchema,
    PollutantReadingSchema,
    StationGeoJsonCollectionSchema,
    StationGeoJsonFeatureSchema,
    StationGeoJsonPropertiesSchema,
)
from app.services.air_quality.aqi_calculator import (
    AQICalculationResult,
    AQIStandard,
    PollutantCode,
    calculate_aqi,
    convert_gas_unit_for_standard,
)
from app.services.air_quality.cache import StaleAwareTelemetryCache, telemetry_cache

PRIORITY_INGESTION_CITIES: tuple[str, ...] = (
    "Delhi",
    "Bengaluru",
    "Mumbai",
    "Chennai",
    "Kolkata",
)


def precaution_for_aqi(standard: AQIStandard, aqi: int | None) -> str:
    if aqi is None:
        return (
            "Verified AQI is currently unavailable. Limit heavy smoke exposure "
            "and check back shortly."
        )
    severe_cutoff = 301 if standard == AQIStandard.INDIA_NAQI else 201
    poor_cutoff = 201 if standard == AQIStandard.INDIA_NAQI else 151
    moderate_cutoff = 101
    if aqi >= severe_cutoff:
        return (
            "Severe pollution: shift exercise indoors, keep windows closed unless filtering, "
            "and wear a well-fitted N95/FFP2 respirator if outdoors."
        )
    if aqi >= poor_cutoff:
        return (
            "Elevated pollution: avoid prolonged outdoor exertion and prioritize enclosed "
            "transit over roadside cycling or walking."
        )
    if aqi >= moderate_cutoff:
        return (
            "Moderate pollution: children, older adults, and sensitive individuals should "
            "reduce prolonged heavy outdoor exertion."
        )
    return "Air quality is suitable for normal outdoor activities."


def calculate_standard_isolated_aqi(
    standard: AQIStandard,
    raw_measurements: dict[PollutantCode, tuple[float, str]],
) -> AQICalculationResult:
    """Convert gaseous units using documented 25°C/1 atm reference before standard-isolated AQI."""
    converted: dict[PollutantCode, tuple[float, str]] = {}
    for code, (conc, unit) in raw_measurements.items():
        norm = convert_gas_unit_for_standard(code, conc, unit, standard)
        if norm is not None:
            converted[code] = norm
    return calculate_aqi(standard=standard, measurements=converted)


class AirQualityTelemetryService:
    """Service orchestrating standard-isolated AQI, caching, staleness, and stations."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        *,
        adapter_client: FailoverAirQualityClient | None = None,
        cache: StaleAwareTelemetryCache | None = None,
    ) -> None:
        self._session = session
        self._repo = TelemetryRepository(session)
        self._settings = settings
        self._adapter = adapter_client or resolve_air_quality_adapter(settings)
        self._cache = cache or telemetry_cache

    @staticmethod
    def _city_slug(city: str) -> str:
        return city.strip().lower().replace(" ", "_")

    async def get_current_air_quality(
        self, *, city: str, standard: AQIStandard
    ) -> CurrentAirQualitySchema:
        cache_key = f"aqi:current:{standard.value}:{self._city_slug(city)}"
        cached_fresh = await self._cache.get_fresh(cache_key, CurrentAirQualitySchema)
        if cached_fresh is not None:
            return cached_fresh

        try:
            raw = await self._adapter.fetch_city_measurements(city)
        except ExternalProviderUnavailableError:
            stale_backup = await self._cache.get_stale_backup(cache_key, CurrentAirQualitySchema)
            if stale_backup is not None:
                return stale_backup.model_copy(update={"is_stale": True})
            raise

        calc = calculate_standard_isolated_aqi(standard, raw.measurements)
        pollutant_items: list[PollutantReadingSchema] = []
        for code, (conc, unit) in raw.measurements.items():
            avg_hours = (
                1
                if standard == AQIStandard.US_EPA and code in {PollutantCode.NO2, PollutantCode.SO2}
                else (8 if code in {PollutantCode.CO, PollutantCode.O3} else 24)
            )
            pollutant_items.append(
                PollutantReadingSchema(
                    pollutant=code,
                    concentration=conc,
                    unit=unit,
                    averaging_period_hours=avg_hours,
                    sub_index=(
                        calc.sub_indices[code].sub_index if code in calc.sub_indices else None
                    ),
                )
            )

        payload = CurrentAirQualitySchema(
            city=raw.city,
            location_precision="city",
            standard=standard,
            status="available" if calc.status == "available" else "unavailable",
            aqi=calc.aqi,
            category=calc.category,
            dominant_pollutant=calc.dominant_pollutant,
            pollutants=pollutant_items,
            measured_at=raw.measured_at,
            provider=raw.provider,
            source_type=raw.source_type,
            is_stale=raw.is_stale or is_timestamp_stale(raw.measured_at),
            is_development_fixture=raw.is_development_fixture,
            precaution_summary=precaution_for_aqi(standard, calc.aqi),
            unavailable_reason=calc.unavailable_reason,
        )
        await self._cache.set_payload(cache_key, payload)
        return payload

    async def get_historical_air_quality(
        self,
        *,
        city: str,
        standard: AQIStandard,
        period: HistoryPeriodLiteral,
    ) -> HistoricalAirQualitySchema:
        cache_key = f"aqi:history:{standard.value}:{period}:{self._city_slug(city)}"
        cached_fresh = await self._cache.get_fresh(cache_key, HistoricalAirQualitySchema)
        if cached_fresh is not None:
            return cached_fresh

        try:
            raw_history = await self._adapter.fetch_city_history(city, period=period)
        except ExternalProviderUnavailableError:
            stale_backup = await self._cache.get_stale_backup(cache_key, HistoricalAirQualitySchema)
            if stale_backup is not None:
                return stale_backup.model_copy(update={"is_stale": True})
            raise

        series: list[HistoricalAirQualityPointSchema] = []
        for point in raw_history.points:
            calc = calculate_standard_isolated_aqi(standard, point.measurements)
            pm25 = point.measurements.get(PollutantCode.PM25)
            pm10 = point.measurements.get(PollutantCode.PM10)
            series.append(
                HistoricalAirQualityPointSchema(
                    timestamp=point.timestamp,
                    aqi=calc.aqi,
                    category=calc.category,
                    pm25_ug_m3=pm25[0] if pm25 and pm25[1] == "ug/m3" else None,
                    pm10_ug_m3=pm10[0] if pm10 and pm10[1] == "ug/m3" else None,
                    dominant_pollutant=calc.dominant_pollutant,
                )
            )

        payload = HistoricalAirQualitySchema(
            city=raw_history.city,
            standard=standard,
            period=period,
            provider=raw_history.provider,
            source_type=raw_history.source_type,
            is_stale=raw_history.is_stale,
            is_development_fixture=raw_history.is_development_fixture,
            series=series,
        )
        await self._cache.set_payload(cache_key, payload, fresh_ttl_seconds=1800)
        return payload

    async def get_air_quality_forecast(
        self,
        *,
        city: str,
        standard: AQIStandard,
        hours: int = 24,
    ) -> AirQualityForecastSchema:
        cache_key = f"aqi:forecast:{standard.value}:{hours}:{self._city_slug(city)}"
        cached_fresh = await self._cache.get_fresh(cache_key, AirQualityForecastSchema)
        if cached_fresh is not None:
            return cached_fresh

        try:
            raw_forecast = await self._adapter.fetch_city_forecast(city, hours=hours)
        except ExternalProviderUnavailableError:
            stale_backup = await self._cache.get_stale_backup(cache_key, AirQualityForecastSchema)
            if stale_backup is not None:
                return stale_backup.model_copy(update={"is_stale": True})
            raise

        calculated_slices = [
            (slc, calculate_standard_isolated_aqi(standard, slc.measurements))
            for slc in raw_forecast.slices
        ]
        valid_aqis = [c.aqi for _, c in calculated_slices if c.aqi is not None]
        min_aqi = min(valid_aqis) if valid_aqis else None
        severe_threshold = 300 if standard == AQIStandard.INDIA_NAQI else 200

        points: list[ForecastPointSchema] = []
        for slc, calc in calculated_slices:
            pm25 = slc.measurements.get(PollutantCode.PM25)
            pm10 = slc.measurements.get(PollutantCode.PM10)
            is_safer = bool(
                calc.aqi is not None
                and calc.aqi <= severe_threshold
                and (calc.aqi <= 100 or (min_aqi is not None and calc.aqi <= min_aqi + 15))
            )
            points.append(
                ForecastPointSchema(
                    forecast_for=slc.forecast_for,
                    aqi=calc.aqi,
                    category=calc.category,
                    dominant_pollutant=calc.dominant_pollutant,
                    pm25_ug_m3=pm25[0] if pm25 and pm25[1] == "ug/m3" else None,
                    pm10_ug_m3=pm10[0] if pm10 and pm10[1] == "ug/m3" else None,
                    confidence_level=slc.confidence_level,
                    safer_outdoor_window=is_safer,
                )
            )

        payload = AirQualityForecastSchema(
            city=raw_forecast.city,
            standard=standard,
            generated_at=raw_forecast.generated_at,
            provider=raw_forecast.provider,
            source_type=raw_forecast.source_type,
            is_stale=raw_forecast.is_stale,
            is_development_fixture=raw_forecast.is_development_fixture,
            points=points,
        )
        await self._cache.set_payload(cache_key, payload, fresh_ttl_seconds=1800)
        return payload

    def _station_to_schema(
        self,
        station: NormalizedStationTelemetry,
        *,
        standard: AQIStandard,
        origin_lat: float | None = None,
        origin_lon: float | None = None,
    ) -> MonitoringStationSchema:
        calc = calculate_standard_isolated_aqi(standard, station.measurements)
        dist = (
            haversine_distance_km(origin_lat, origin_lon, station.latitude, station.longitude)
            if origin_lat is not None and origin_lon is not None
            else None
        )
        return MonitoringStationSchema(
            station_id=station.external_station_id,
            name=station.name,
            city=station.city,
            state_region=station.state_region,
            country_code=station.country_code,
            latitude=station.latitude,
            longitude=station.longitude,
            distance_km=dist,
            provider=station.provider,
            source_type=station.source_type,
            standard=standard,
            aqi=calc.aqi,
            category=calc.category,
            dominant_pollutant=calc.dominant_pollutant,
            measured_at=station.measured_at,
            is_stale=station.is_stale or is_timestamp_stale(station.measured_at),
            is_development_fixture=station.is_development_fixture,
        )

    async def get_nearby_stations(
        self,
        *,
        standard: AQIStandard,
        city: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        radius_km: float = 25.0,
    ) -> list[MonitoringStationSchema]:
        target_city = city
        origin_lat = latitude
        origin_lon = longitude

        if target_city is None and origin_lat is not None and origin_lon is not None:
            ref_lat = origin_lat
            ref_lon = origin_lon
            closest = min(
                CITY_COORDINATE_GAZETTEER.values(),
                key=lambda c: haversine_distance_km(ref_lat, ref_lon, c.latitude, c.longitude),
            )
            target_city = closest.city
        elif target_city is not None and (origin_lat is None or origin_lon is None):
            centroid = lookup_city_centroid(target_city)
            if centroid is not None:
                origin_lat = centroid.latitude
                origin_lon = centroid.longitude

        if not target_city:
            raise AirWiseError(
                code="VALIDATION_ERROR",
                message="Provide either a city name or latitude/longitude coordinates.",
                status_code=422,
            )

        raw_stations = await self._adapter.fetch_city_stations(target_city)
        for st in raw_stations:
            await self._repo.upsert_station_with_measurements(st)
        await self._session.commit()

        mapped = [
            self._station_to_schema(
                st,
                standard=standard,
                origin_lat=origin_lat,
                origin_lon=origin_lon,
            )
            for st in raw_stations
        ]
        filtered = [
            item for item in mapped if item.distance_km is None or item.distance_km <= radius_km
        ]
        filtered.sort(key=lambda s: s.distance_km if s.distance_km is not None else 0.0)
        return filtered

    async def get_stations_geojson(
        self,
        *,
        standard: AQIStandard,
        bbox: str | None = None,
        city: str | None = None,
    ) -> StationGeoJsonCollectionSchema:
        stations_list: list[MonitoringStationSchema] = []
        if city:
            stations_list = await self.get_nearby_stations(
                standard=standard, city=city, radius_km=50.0
            )
        elif bbox:
            parts = [p.strip() for p in bbox.split(",")]
            if len(parts) != 4:
                raise AirWiseError(
                    code="VALIDATION_ERROR",
                    message=(
                        "bbox must contain 4 comma-separated numbers: minLon,minLat,maxLon,maxLat."
                    ),
                    status_code=422,
                )
            try:
                min_lon, min_lat, max_lon, max_lat = (float(p) for p in parts)
            except ValueError as exc:
                raise AirWiseError(
                    code="VALIDATION_ERROR",
                    message="bbox coordinates must be valid numbers.",
                    status_code=422,
                ) from exc
            if min_lon > max_lon or min_lat > max_lat:
                raise AirWiseError(
                    code="VALIDATION_ERROR",
                    message="bbox min coordinates must not exceed max coordinates.",
                    status_code=422,
                )

            # Warm stations for any gazetteer city falling inside the requested bounding box
            matching_cities = [
                c.city
                for c in CITY_COORDINATE_GAZETTEER.values()
                if min_lat <= c.latitude <= max_lat and min_lon <= c.longitude <= max_lon
            ]
            for c_name in matching_cities[:5]:
                city_stations = await self.get_nearby_stations(
                    standard=standard, city=c_name, radius_km=50.0
                )
                stations_list.extend(
                    st
                    for st in city_stations
                    if min_lat <= st.latitude <= max_lat and min_lon <= st.longitude <= max_lon
                )

            if not stations_list:
                db_rows = await self._repo.list_stations_in_bbox(
                    min_lon=min_lon,
                    min_lat=min_lat,
                    max_lon=max_lon,
                    max_lat=max_lat,
                )
                for st_row, provider_slug, meas, latest_ts, is_fix in db_rows:
                    calc = calculate_standard_isolated_aqi(standard, meas)
                    source_lit: Literal["station", "model"] = (
                        "model" if st_row.source_type == "model" else "station"
                    )
                    stations_list.append(
                        MonitoringStationSchema(
                            station_id=st_row.external_station_id,
                            name=st_row.name,
                            city=st_row.city,
                            state_region=st_row.state_region,
                            country_code=st_row.country_code,
                            latitude=st_row.latitude,
                            longitude=st_row.longitude,
                            provider=provider_slug,
                            source_type=source_lit,
                            standard=standard,
                            aqi=calc.aqi,
                            category=calc.category,
                            dominant_pollutant=calc.dominant_pollutant,
                            measured_at=latest_ts,
                            is_stale=(
                                is_timestamp_stale(latest_ts) if latest_ts is not None else True
                            ),
                            is_development_fixture=is_fix,
                        )
                    )
        else:
            stations_list = await self.get_nearby_stations(
                standard=standard, city="Delhi", radius_km=50.0
            )

        any_fixture = any(st.is_development_fixture for st in stations_list)
        features = [
            StationGeoJsonFeatureSchema(
                geometry=GeoJsonPointGeometrySchema(coordinates=(st.longitude, st.latitude)),
                properties=StationGeoJsonPropertiesSchema(
                    station_id=st.station_id,
                    name=st.name,
                    city=st.city,
                    provider=st.provider,
                    source_type=st.source_type,
                    standard=standard,
                    aqi=st.aqi,
                    category=st.category,
                    dominant_pollutant=st.dominant_pollutant,
                    measured_at=st.measured_at,
                    is_stale=st.is_stale,
                    is_development_fixture=st.is_development_fixture,
                ),
            )
            for st in stations_list
        ]
        return StationGeoJsonCollectionSchema(
            standard=standard,
            is_development_fixture=any_fixture,
            features=features,
        )

    async def ingest_priority_cities(
        self, cities: tuple[str, ...] = PRIORITY_INGESTION_CITIES
    ) -> dict[str, int]:
        ingested_cities = 0
        persisted_stations = 0
        for city in cities:
            try:
                stations = await self._adapter.fetch_city_stations(city)
                for st in stations:
                    await self._repo.upsert_station_with_measurements(st)
                    persisted_stations += 1
                await self.get_current_air_quality(city=city, standard=AQIStandard.INDIA_NAQI)
                await self.get_current_air_quality(city=city, standard=AQIStandard.US_EPA)
                ingested_cities += 1
            except ExternalProviderUnavailableError:
                continue
        await self._session.commit()
        return {
            "cities_refreshed": ingested_cities,
            "stations_persisted": persisted_stations,
            "timestamp_epoch": int(datetime.now(tz=UTC).timestamp()),
        }
