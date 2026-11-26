from __future__ import annotations

from dataclasses import asdict, dataclass, field
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.rag.knowledge import KnowledgeService, RetrievedEvidence
from app.ai.tools.registry import ALLOWLISTED_AI_TOOLS, ToolAuthScope
from app.core.config import Settings
from app.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ExternalProviderUnavailableError,
)
from app.repositories.identity_repository import IdentityRepository
from app.schemas.air_quality import CurrentAirQualitySchema
from app.schemas.assistant import ChatRequest, ToolCall
from app.services.air_quality.telemetry_service import AirQualityTelemetryService
from app.services.impact.calculators import (
    ImpactResult,
    calculate_transport_emissions,
    estimate_relative_exposure_change,
)
from app.services.recommendations.recommendation_service import HybridRecommendationService
from app.services.routines.routine_service import RoutinePlannerService
from app.services.weather.weather_service import WeatherTelemetryService


@dataclass
class ToolExecutor:
    session: AsyncSession
    settings: Settings
    user_id: UUID | None
    request: ChatRequest
    knowledge: KnowledgeService
    current: CurrentAirQualitySchema | None = None
    evidence: list[RetrievedEvidence] = field(default_factory=list)
    impact: ImpactResult | None = None
    vulnerable: bool = False
    results: dict[str, dict[str, object]] = field(default_factory=dict)

    async def execute(self, call: ToolCall) -> dict[str, object]:
        spec = next(tool for tool in ALLOWLISTED_AI_TOOLS if tool.name == call.name)
        if spec.auth_scope == ToolAuthScope.AUTHENTICATED_SELF and self.user_id is None:
            raise AuthenticationError()
        if spec.requires_preference_consent and not self.request.use_preferences:
            raise AuthorizationError(
                code="AI_PREFERENCE_CONSENT_REQUIRED",
                message="Explicit permission is required to use household preferences.",
            )
        key = f"{call.name}:{call.period}:{call.hours}"
        if key in self.results:
            return self.results[key]
        try:
            result = await self._execute(call)
        except ExternalProviderUnavailableError as exc:
            result = {"status": "unavailable", "reason": exc.message, "code": exc.code}
        self.results[key] = result
        return result

    async def _execute(self, call: ToolCall) -> dict[str, object]:
        name = call.name
        if name == "get_current_air_quality":
            if self.request.city is None:
                return {"status": "unavailable", "reason": "No city was selected."}
            self.current = await AirQualityTelemetryService(
                self.session, self.settings
            ).get_current_air_quality(city=self.request.city, standard=self.request.standard)
            return self.current.model_dump(mode="json")
        if name in {"get_air_quality_forecast", "get_historical_air_quality"}:
            if self.request.city is None:
                return {"status": "unavailable", "reason": "No city was selected."}
            service = AirQualityTelemetryService(self.session, self.settings)
            if name == "get_air_quality_forecast":
                forecast = await service.get_air_quality_forecast(
                    city=self.request.city, standard=self.request.standard, hours=call.hours
                )
                return forecast.model_dump(mode="json")
            history = await service.get_historical_air_quality(
                city=self.request.city, standard=self.request.standard, period=call.period
            )
            return history.model_dump(mode="json")
        if name == "get_weather_conditions":
            if self.request.city is None:
                return {"status": "unavailable", "reason": "No city was selected."}
            weather = await WeatherTelemetryService(
                self.session, self.settings
            ).get_current_weather(city=self.request.city)
            return weather.model_dump(mode="json")
        if name == "get_saved_locations":
            if self.user_id is None:
                raise AuthenticationError()
            locations = await IdentityRepository(self.session).list_saved_locations(
                user_id=self.user_id
            )
            return {
                "locations": [
                    {"city": row.city, "country_code": row.country_code} for row in locations
                ]
            }
        if name == "get_user_preferences":
            if self.user_id is None:
                raise AuthenticationError()
            user = await IdentityRepository(self.session).get_user_by_id(self.user_id)
            prefs = user.preferences if user else None
            if prefs is None or prefs.consent_updated_at is None:
                return {"status": "unavailable", "reason": "No consented preferences were saved."}
            self.vulnerable = bool(prefs.has_vulnerable_members)
            return {
                "has_vulnerable_members": self.vulnerable,
                "has_hepa_purifier": prefs.has_hepa_purifier,
                "budget_tier": prefs.budget_tier,
            }
        if name == "retrieve_environmental_guidelines":
            self.evidence = await self.knowledge.retrieve(
                self.request.message,
                jurisdiction="IN" if self.request.standard.value == "india_naqi" else "US",
            )
            return {
                "status": "available" if self.evidence else "unavailable",
                "evidence": [
                    {"reference": item.reference.model_dump(mode="json"), "content": item.content}
                    for item in self.evidence
                ],
            }
        calculation = self.request.calculation
        if (
            name == "calculate_transport_emissions"
            and calculation is not None
            and calculation.kind == "transport"
        ):
            self.impact = calculate_transport_emissions(**calculation.model_dump(exclude={"kind"}))
            return asdict(self.impact)
        if (
            name == "estimate_exposure_change"
            and calculation is not None
            and calculation.kind == "exposure"
        ):
            self.impact = estimate_relative_exposure_change(
                **calculation.model_dump(exclude={"kind"})
            )
            return asdict(self.impact)
        if name == "compare_daily_routines":
            if self.user_id is None:
                raise AuthenticationError()
            planner = RoutinePlannerService(self.session, self.settings)
            if self.request.city is not None:
                comparison = await planner.compare_routine_windows(
                    city=self.request.city,
                    standard=self.request.standard,
                    has_vulnerable_member=self.vulnerable,
                )
                return {
                    "status": "available",
                    "comparison": comparison.model_dump(mode="json"),
                }
            saved_routines = await planner.list_routines(user_id=self.user_id)
            if saved_routines:
                latest = saved_routines[0]
                comparison = await planner.compare_routine_windows(
                    city=latest.city,
                    standard=latest.aqi_standard,
                    has_vulnerable_member=self.vulnerable,
                )
                return {
                    "status": "available",
                    "comparison": comparison.model_dump(mode="json"),
                }
            return {
                "status": "unavailable",
                "reason": "Select a city or save a routine first to compare daily time blocks.",
            }
        if name == "generate_sustainable_alternatives":
            rec_service = HybridRecommendationService(self.session, self.settings)
            options = await rec_service.generate_screened_alternatives(
                city=self.request.city,
                standard=self.request.standard,
            )
            return {
                "status": "available",
                "alternatives": [opt.model_dump(mode="json") for opt in options],
            }
        return {
            "status": "unavailable",
            "reason": (
                "Explicit structured calculation inputs and source assumptions are required."
                if name in {"calculate_transport_emissions", "estimate_exposure_change"}
                else "Community initiatives service is scheduled for Phase 6. "
                "No results or saved changes are being claimed."
            ),
        }
