"""Weather telemetry service with stale-aware caching and thermal inversion flags."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ExternalProviderUnavailableError
from app.integrations.weather.provider import (
    FailoverWeatherClient,
    resolve_weather_adapter,
)
from app.repositories.telemetry_repository import TelemetryRepository
from app.schemas.weather import CurrentWeatherSchema
from app.services.air_quality.cache import StaleAwareTelemetryCache, telemetry_cache


def build_dispersion_note(
    *, inversion_risk: bool, wind_speed_mps: float, humidity_pct: float
) -> str:
    if inversion_risk:
        return (
            "Calm winds and cool, humid air indicate elevated winter thermal-inversion "
            "stagnation risk—surface PM2.5 disperses slowly overnight and early morning."
        )
    if wind_speed_mps >= 3.5:
        return "Moderate-to-brisk surface winds are aiding horizontal pollutant dispersion."
    if humidity_pct >= 75.0:
        return "High relative humidity can accelerate hygroscopic aerosol haze growth."
    return "Typical urban boundary-layer dispersion conditions."


class WeatherTelemetryService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        *,
        adapter_client: FailoverWeatherClient | None = None,
        cache: StaleAwareTelemetryCache | None = None,
    ) -> None:
        self._session = session
        self._repo = TelemetryRepository(session)
        self._adapter = adapter_client or resolve_weather_adapter(settings)
        self._cache = cache or telemetry_cache

    async def get_current_weather(self, *, city: str) -> CurrentWeatherSchema:
        slug = city.strip().lower().replace(" ", "_")
        cache_key = f"weather:current:{slug}"
        cached = await self._cache.get_fresh(cache_key, CurrentWeatherSchema)
        if cached is not None:
            return cached

        try:
            raw = await self._adapter.fetch_city_weather(city)
        except ExternalProviderUnavailableError:
            stale = await self._cache.get_stale_backup(cache_key, CurrentWeatherSchema)
            if stale is not None:
                return stale.model_copy(update={"is_stale": True})
            raise

        await self._repo.record_weather_observation(raw)
        await self._session.commit()

        payload = CurrentWeatherSchema(
            city=raw.city,
            temperature_c=raw.temperature_c,
            humidity_pct=raw.humidity_pct,
            wind_speed_mps=raw.wind_speed_mps,
            wind_direction_deg=raw.wind_direction_deg,
            inversion_risk_flag=raw.inversion_risk_flag,
            dispersion_note=build_dispersion_note(
                inversion_risk=raw.inversion_risk_flag,
                wind_speed_mps=raw.wind_speed_mps,
                humidity_pct=raw.humidity_pct,
            ),
            observed_at=raw.observed_at,
            provider=raw.provider,
            is_stale=raw.is_stale,
            is_development_fixture=raw.is_development_fixture,
        )
        await self._cache.set_payload(cache_key, payload, fresh_ttl_seconds=900)
        return payload
