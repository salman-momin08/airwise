from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from app.core.config import Settings
from app.core.exceptions import ExternalProviderUnavailableError
from app.services.air_quality.aqi_calculator import PollutantCode


@dataclass(frozen=True)
class NormalizedProviderPayload:
    city: str
    provider: str
    source_type: str  # "station" | "model"
    measured_at: datetime
    is_stale: bool
    is_development_fixture: bool
    measurements: dict[PollutantCode, tuple[float, str]]


class AirQualityProviderAdapter(Protocol):
    async def fetch_city_measurements(self, city: str) -> NormalizedProviderPayload: ...


class DevelopmentFixtureAirQualityAdapter:
    """Explicitly labeled development fixture adapter.

    Prohibited in production by Settings.validate_production_invariants().
    Every reading sets is_development_fixture=True so UI never mistakes it for live telemetry.
    """

    FIXTURE_CITIES: dict[str, dict[PollutantCode, tuple[float, str]]] = {
        "delhi": {
            PollutantCode.PM25: (192.0, "ug/m3"),
            PollutantCode.PM10: (318.0, "ug/m3"),
            PollutantCode.NO2: (76.0, "ug/m3"),
            PollutantCode.SO2: (18.0, "ug/m3"),
            PollutantCode.CO: (1.8, "mg/m3"),
            PollutantCode.O3: (42.0, "ug/m3"),
        },
        "bengaluru": {
            PollutantCode.PM25: (28.0, "ug/m3"),
            PollutantCode.PM10: (58.0, "ug/m3"),
            PollutantCode.NO2: (31.0, "ug/m3"),
            PollutantCode.SO2: (9.0, "ug/m3"),
            PollutantCode.CO: (0.7, "mg/m3"),
            PollutantCode.O3: (46.0, "ug/m3"),
        },
    }

    async def fetch_city_measurements(self, city: str) -> NormalizedProviderPayload:
        key = city.strip().lower()
        sample = self.FIXTURE_CITIES.get(key)
        if sample is None:
            raise ExternalProviderUnavailableError(
                code="AIR_QUALITY_FIXTURE_CITY_NOT_CONFIGURED",
                message=(
                    f"No development fixture exists for '{city}'. Configure AIR_QUALITY_API_KEY "
                    "and AIR_QUALITY_PROVIDER=openaq for live city telemetry."
                ),
            )
        return NormalizedProviderPayload(
            city=city.strip().title(),
            provider="development_fixture",
            source_type="station",
            measured_at=datetime.now(tz=UTC),
            is_stale=False,
            is_development_fixture=True,
            measurements=sample,
        )


def resolve_air_quality_adapter(settings: Settings) -> AirQualityProviderAdapter:
    if settings.air_quality_provider == "fixture":
        return DevelopmentFixtureAirQualityAdapter()
    if not settings.air_quality_api_key:
        raise ExternalProviderUnavailableError(
            code="AIR_QUALITY_CREDENTIALS_MISSING",
            message="Live air quality provider credentials are not configured.",
        )
    raise ExternalProviderUnavailableError(
        code="AIR_QUALITY_PROVIDER_NOT_INITIALIZED",
        message="Live provider adapter awaits Phase 3 credential onboarding.",
    )
