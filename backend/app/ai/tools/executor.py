"""Deterministic execution engine for the 12 allowlisted AirWise Copilot tools."""

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
from app.services.community.community_service import CommunityService
from app.services.impact.calculators import (
    ImpactResult,
    calculate_transport_emissions,
    estimate_relative_exposure_change,
)
from app.services.recommendations.recommendation_service import HybridRecommendationService
from app.services.routines.routine_service import RoutinePlannerService
from app.services.weather.weather_service import WeatherTelemetryService

_MISSING_CALCULATION_INPUTS = {
    "status": "unavailable",
    "reason": "Explicit structured calculation inputs and source assumptions are required.",
}


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
            raise AuthenticationError
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

    def _require_user_id(self) -> UUID:
        if self.user_id is None:
            raise AuthenticationError
        return self.user_id

    async def _tool_current_aqi(self, _call: ToolCall) -> dict[str, object]:
        if self.request.city is None:
            return {"status": "unavailable", "reason": "No city was selected."}
        self.current = await AirQualityTelemetryService(
            self.session, self.settings
        ).get_current_air_quality(city=self.request.city, standard=self.request.standard)
        return self.current.model_dump(mode="json")

    async def _tool_forecast_aqi(self, call: ToolCall) -> dict[str, object]:
        if self.request.city is None:
            return {"status": "unavailable", "reason": "No city was selected."}
        forecast = await AirQualityTelemetryService(
            self.session, self.settings
        ).get_air_quality_forecast(
            city=self.request.city, standard=self.request.standard, hours=call.hours
        )
        return forecast.model_dump(mode="json")

    async def _tool_history_aqi(self, call: ToolCall) -> dict[str, object]:
        if self.request.city is None:
            return {"status": "unavailable", "reason": "No city was selected."}
        history = await AirQualityTelemetryService(
            self.session, self.settings
        ).get_historical_air_quality(
            city=self.request.city, standard=self.request.standard, period=call.period
        )
        return history.model_dump(mode="json")

    async def _tool_weather(self, _call: ToolCall) -> dict[str, object]:
        if self.request.city is None:
            return {"status": "unavailable", "reason": "No city was selected."}
        weather = await WeatherTelemetryService(self.session, self.settings).get_current_weather(
            city=self.request.city
        )
        return weather.model_dump(mode="json")

    async def _tool_saved_locations(self, _call: ToolCall) -> dict[str, object]:
        locations = await IdentityRepository(self.session).list_saved_locations(
            user_id=self._require_user_id()
        )
        return {
            "locations": [{"city": row.city, "country_code": row.country_code} for row in locations]
        }

    async def _tool_user_preferences(self, _call: ToolCall) -> dict[str, object]:
        user = await IdentityRepository(self.session).get_user_by_id(self._require_user_id())
        prefs = user.preferences if user else None
        if prefs is None or prefs.consent_updated_at is None:
            return {"status": "unavailable", "reason": "No consented preferences were saved."}
        self.vulnerable = bool(prefs.has_vulnerable_members)
        return {
            "has_vulnerable_members": self.vulnerable,
            "has_hepa_purifier": prefs.has_hepa_purifier,
            "budget_tier": prefs.budget_tier,
        }

    async def _tool_retrieve_guidelines(self, _call: ToolCall) -> dict[str, object]:
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

    async def _tool_transport_emissions(self, _call: ToolCall) -> dict[str, object]:
        calc = self.request.calculation
        if calc is None or calc.kind != "transport":
            return dict(_MISSING_CALCULATION_INPUTS)
        self.impact = calculate_transport_emissions(**calc.model_dump(exclude={"kind"}))
        return asdict(self.impact)

    async def _tool_exposure_change(self, _call: ToolCall) -> dict[str, object]:
        calc = self.request.calculation
        if calc is None or calc.kind != "exposure":
            return dict(_MISSING_CALCULATION_INPUTS)
        self.impact = estimate_relative_exposure_change(**calc.model_dump(exclude={"kind"}))
        return asdict(self.impact)

    async def _tool_compare_routines(self, _call: ToolCall) -> dict[str, object]:
        uid = self._require_user_id()
        planner = RoutinePlannerService(self.session, self.settings)
        target_city = self.request.city
        target_standard = self.request.standard
        if target_city is None:
            saved_routines = await planner.list_routines(user_id=uid)
            if not saved_routines:
                return {
                    "status": "unavailable",
                    "reason": "Select a city or save a routine first to compare daily time blocks.",
                }
            target_city = saved_routines[0].city
            target_standard = saved_routines[0].aqi_standard

        comparison = await planner.compare_routine_windows(
            city=target_city,
            standard=target_standard,
            has_vulnerable_member=self.vulnerable,
        )
        return {"status": "available", "comparison": comparison.model_dump(mode="json")}

    async def _tool_sustainable_alternatives(self, _call: ToolCall) -> dict[str, object]:
        rec_service = HybridRecommendationService(self.session, self.settings)
        options = await rec_service.generate_screened_alternatives(
            city=self.request.city,
            standard=self.request.standard,
        )
        return {
            "status": "available",
            "alternatives": [opt.model_dump(mode="json") for opt in options],
        }

    async def _tool_community_initiatives(self, _call: ToolCall) -> dict[str, object]:
        comm_service = CommunityService(self.session, self.settings)
        initiatives = await comm_service.list_public_initiatives_for_ai(city=self.request.city)
        return {
            "status": "available",
            "initiatives": [item.model_dump(mode="json") for item in initiatives],
            "privacy_notice": (
                "Aggregate self-reported participation only; never claims measured city AQI change."
            ),
        }

    async def _execute(self, call: ToolCall) -> dict[str, object]:
        dispatch = {
            "get_current_air_quality": self._tool_current_aqi,
            "get_air_quality_forecast": self._tool_forecast_aqi,
            "get_historical_air_quality": self._tool_history_aqi,
            "get_weather_conditions": self._tool_weather,
            "get_saved_locations": self._tool_saved_locations,
            "get_user_preferences": self._tool_user_preferences,
            "retrieve_environmental_guidelines": self._tool_retrieve_guidelines,
            "calculate_transport_emissions": self._tool_transport_emissions,
            "estimate_exposure_change": self._tool_exposure_change,
            "compare_daily_routines": self._tool_compare_routines,
            "generate_sustainable_alternatives": self._tool_sustainable_alternatives,
            "get_community_initiatives": self._tool_community_initiatives,
        }
        handler = dispatch.get(call.name)
        if handler is None:
            return dict(_MISSING_CALCULATION_INPUTS)
        return await handler(call)
