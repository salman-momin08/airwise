"""Hybrid deterministic + safety-gated AI phrasing recommendation service."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.gateway.budget import TokenBudget
from app.ai.gateway.gemini import GeminiGateway, LLMGateway, OutputValidationError
from app.core.config import Settings
from app.core.exceptions import AuthorizationError, ExternalProviderUnavailableError
from app.models.assistant import KnowledgeDocument
from app.models.planning import ImpactEstimate, Recommendation
from app.repositories.identity_repository import IdentityRepository
from app.repositories.planning_repository import PlanningRepository
from app.schemas.air_quality import AirQualityForecastSchema, CurrentAirQualitySchema
from app.schemas.assistant import EvidenceReference
from app.schemas.impact import (
    HouseholdEnergyImpactRequest,
    IndoorFiltrationImpactRequest,
    TransportImpactRequest,
)
from app.schemas.recommendations import (
    GeneratedRecommendationsBatch,
    GenerateRecommendationsRequest,
    RecommendationCardSchema,
    RecommendationCategoryLiteral,
    RecommendationFeedbackRequest,
    RecommendationFeedbackSchema,
    RecommendationFeedbackStatusLiteral,
    RecommendationPriorityLiteral,
    ScreenedAlternativeSchema,
)
from app.schemas.weather import CurrentWeatherSchema
from app.services.air_quality.aqi_calculator import AQIStandard
from app.services.air_quality.telemetry_service import AirQualityTelemetryService
from app.services.impact.impact_service import ImpactEngineService, serialize_impact_record
from app.services.recommendations.card_templates import (
    PRIORITY_ORDER,
    build_deterministic_card_specs,
    build_screened_transport_alternatives,
    is_safe_ai_reason,
)
from app.services.recommendations.safety_engine import (
    EnvironmentalRuleContext,
    evaluate_environmental_rules,
)
from app.services.weather.weather_service import WeatherTelemetryService

logger = structlog.get_logger(__name__)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class HybridRecommendationService:
    """Generates deterministic + optional Gemini-phrased cards across all 5 categories."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        *,
        gateway: LLMGateway | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._repo = PlanningRepository(session)
        self._identity_repo = IdentityRepository(session)
        self._impact_service = ImpactEngineService(session, settings)
        self._gateway = gateway

    async def _fetch_telemetry(
        self, *, city: str, standard: AQIStandard
    ) -> tuple[
        CurrentAirQualitySchema | None,
        AirQualityForecastSchema | None,
        CurrentWeatherSchema | None,
    ]:
        aq = AirQualityTelemetryService(self._session, self._settings)
        wx = WeatherTelemetryService(self._session, self._settings)
        try:
            current = await aq.get_current_air_quality(city=city, standard=standard)
        except ExternalProviderUnavailableError:
            current = None
        try:
            forecast = await aq.get_air_quality_forecast(city=city, standard=standard, hours=24)
        except ExternalProviderUnavailableError:
            forecast = None
        try:
            weather = await wx.get_current_weather(city=city)
        except ExternalProviderUnavailableError:
            weather = None
        return current, forecast, weather

    async def _resolve_verified_documents(
        self, *, standard: AQIStandard
    ) -> tuple[list[str], dict[str, EvidenceReference]]:
        target_jurisdiction = "IN" if standard == AQIStandard.INDIA_NAQI else "US"
        docs = list(
            await self._session.scalars(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.trust_classification == "tier1_official"
                )
            )
        )
        preferred = sorted(
            docs,
            key=lambda d: (0 if d.jurisdiction in {target_jurisdiction, "global"} else 1, d.title),
        )[:3]
        by_id: dict[str, EvidenceReference] = {}
        ids: list[str] = []
        for doc in preferred:
            doc_id_str = str(doc.id)
            ids.append(doc_id_str)
            by_id[doc_id_str] = EvidenceReference(
                document_id=doc.id,
                title=doc.title,
                publisher=doc.publisher,
                source_url=doc.source_url,
                last_reviewed_date=_ensure_utc(doc.last_reviewed_date),
            )
        return ids, by_id

    async def _load_references_by_ids(
        self, doc_ids: set[uuid.UUID]
    ) -> dict[str, EvidenceReference]:
        if not doc_ids:
            return {}
        docs = await self._session.scalars(
            select(KnowledgeDocument).where(KnowledgeDocument.id.in_(doc_ids))
        )
        return {
            str(doc.id): EvidenceReference(
                document_id=doc.id,
                title=doc.title,
                publisher=doc.publisher,
                source_url=doc.source_url,
                last_reviewed_date=_ensure_utc(doc.last_reviewed_date),
            )
            for doc in docs
        }

    async def _serialize_cards(
        self, records: list[Recommendation]
    ) -> list[RecommendationCardSchema]:
        est_ids = {rec.impact_estimate_id for rec in records if rec.impact_estimate_id is not None}
        estimates: dict[uuid.UUID, ImpactEstimate] = await self._repo.get_impact_estimates_by_ids(
            est_ids
        )
        all_doc_uuids: set[uuid.UUID] = set()
        for rec in records:
            for raw_id in rec.evidence_document_ids:
                try:
                    all_doc_uuids.add(uuid.UUID(raw_id))
                except ValueError:
                    continue
        refs_map = await self._load_references_by_ids(all_doc_uuids)

        ordered = sorted(
            records,
            key=lambda r: (PRIORITY_ORDER.get(r.priority, 99), r.category),
        )
        cards: list[RecommendationCardSchema] = []
        for rec in ordered:
            latest_fb: RecommendationFeedbackStatusLiteral | None = None
            if rec.feedback_entries:
                newest = max(rec.feedback_entries, key=lambda f: _ensure_utc(f.created_at))
                if newest.status in {"helpful", "not_relevant", "completed", "dismissed"}:
                    latest_fb = cast(RecommendationFeedbackStatusLiteral, newest.status)

            std = (
                AQIStandard.US_EPA
                if rec.aqi_standard == AQIStandard.US_EPA.value
                else AQIStandard.INDIA_NAQI
            )
            est = (
                estimates.get(rec.impact_estimate_id)
                if rec.impact_estimate_id is not None
                else None
            )
            card_refs = [
                refs_map[doc_id] for doc_id in rec.evidence_document_ids if doc_id in refs_map
            ]
            cards.append(
                RecommendationCardSchema(
                    id=rec.id,
                    city=rec.city,
                    aqi_standard=std,
                    category=cast(RecommendationCategoryLiteral, rec.category),
                    priority=cast(RecommendationPriorityLiteral, rec.priority),
                    title=rec.title,
                    reason=rec.reason,
                    action_steps=list(rec.action_steps),
                    safer_alternative=rec.safer_alternative,
                    uncertainty_note=rec.uncertainty_note,
                    impact_estimate=serialize_impact_record(est) if est is not None else None,
                    evidence_references=card_refs,
                    is_ai_enriched=rec.is_ai_enriched,
                    latest_feedback=latest_fb,
                    valid_until=_ensure_utc(rec.valid_until),
                    created_at=_ensure_utc(rec.created_at),
                )
            )
        return cards

    async def get_today_recommendations(
        self, *, user_id: uuid.UUID
    ) -> list[RecommendationCardSchema]:
        now = datetime.now(tz=UTC)
        records = await self._repo.list_active_recommendations(user_id=user_id, now=now)
        return await self._serialize_cards(records)

    async def generate_recommendations(
        self,
        *,
        user_id: uuid.UUID,
        payload: GenerateRecommendationsRequest,
    ) -> list[RecommendationCardSchema]:
        if payload.use_ai_phrasing and not payload.ai_consent:
            raise AuthorizationError(
                code="AI_CONSENT_REQUIRED",
                message="Explicit AI consent is required when use_ai_phrasing is enabled.",
            )

        user = await self._identity_repo.get_user_by_id(user_id)
        prefs = user.preferences if user is not None else None
        consented = prefs is not None and prefs.consent_updated_at is not None

        current, forecast, weather = await self._fetch_telemetry(
            city=payload.city, standard=payload.standard
        )
        rules: EnvironmentalRuleContext = evaluate_environmental_rules(
            standard=payload.standard,
            current=current,
            weather=weather,
            forecast=forecast,
            has_vulnerable_member=(
                bool(prefs.has_vulnerable_members) if consented and prefs else False
            ),
            age_category=prefs.age_category if consented and prefs else None,
            has_hepa_purifier=bool(prefs.has_hepa_purifier) if consented and prefs else False,
            budget_tier=prefs.budget_tier if consented and prefs else None,
            cooking_type=prefs.cooking_type if consented and prefs else None,
        )

        # Deterministic impact estimates (LLM-immutable)
        transport_res, _ = await self._impact_service.calculate(
            TransportImpactRequest(
                distance_km=payload.commute_distance_km,
                baseline_mode="car_solo_petrol",
                alternative_mode="metro_rail",
                city=payload.city,
                standard=payload.standard,
            )
        )
        transport_est = await self._impact_service.persist_impact_result(
            user_id=user_id, user_action_id=None, result=transport_res
        )

        filtration_res, _ = await self._impact_service.calculate(
            IndoorFiltrationImpactRequest(
                calculator_type="indoor_filtration",
                room_area_m2=18.0,
                ceiling_height_m=2.7,
                cadr_m3_per_hour=250.0,
            )
        )
        filtration_est = await self._impact_service.persist_impact_result(
            user_id=user_id, user_action_id=None, result=filtration_res
        )

        grid_code: Literal["india_cea_grid_avg", "us_epa_egrid_avg"] = (
            "india_cea_grid_avg"
            if payload.standard == AQIStandard.INDIA_NAQI
            else "us_epa_egrid_avg"
        )
        energy_res, _ = await self._impact_service.calculate(
            HouseholdEnergyImpactRequest(
                calculator_type="household_energy",
                baseline_power_kw=1.8,
                alternative_power_kw=1.1,
                operating_hours=4.0,
                grid_region_code=grid_code,
            )
        )
        energy_est = await self._impact_service.persist_impact_result(
            user_id=user_id, user_action_id=None, result=energy_res
        )

        doc_ids, _ = await self._resolve_verified_documents(standard=payload.standard)
        draft_specs = build_deterministic_card_specs(
            rules=rules,
            transport_estimate_id=transport_est.id,
            filtration_estimate_id=filtration_est.id,
            energy_estimate_id=energy_est.id,
        )

        enriched_categories: set[str] = set()
        if (
            payload.use_ai_phrasing
            and payload.ai_consent
            and not rules.block_outdoor_exertion
            and (self._gateway is not None or bool(self._settings.gemini_api_key))
        ):
            gateway = self._gateway or GeminiGateway(
                self._settings, budget=TokenBudget(self._settings, user_id)
            )
            try:
                ai_batch = await gateway.generate(
                    system=(
                        "Rewrite concise, empathetic plain-language 'reason' explanations for each "
                        "environmental recommendation category. Do not include any digits, "
                        "number words, URLs, HTML, clinical diagnoses, houseplant myths, ozone "
                        "cleaners, or claims that household actions lower city AQI."
                    ),
                    prompt=json.dumps(
                        {
                            "standard": payload.standard.value,
                            "severity_tier": rules.severity_tier,
                            "cards": [
                                {
                                    "category": cat,
                                    "title": spec["title"],
                                    "base_reason": spec["reason"],
                                }
                                for cat, spec in draft_specs.items()
                            ],
                        }
                    ),
                    schema=GeneratedRecommendationsBatch,
                )
                for item in ai_batch.cards:
                    if item.category in draft_specs and is_safe_ai_reason(item.reason):
                        draft_specs[item.category]["reason"] = item.reason
                        enriched_categories.add(item.category)
            except (ExternalProviderUnavailableError, OutputValidationError, ValueError) as exc:
                logger.warning("recommendation_ai_phrasing_fallback", error_type=type(exc).__name__)

        now = datetime.now(tz=UTC)
        city_name = current.city if current is not None else payload.city
        await self._repo.expire_active_recommendations_for_city(
            user_id=user_id, city=city_name, now=now
        )
        valid_until = now + timedelta(hours=18)

        created_records: list[Recommendation] = []
        for category, spec in draft_specs.items():
            rec = Recommendation(
                id=uuid.uuid4(),
                user_id=user_id,
                city=city_name,
                aqi_standard=payload.standard.value,
                category=category,
                priority=str(spec["priority"]),
                title=str(spec["title"]),
                reason=str(spec["reason"]),
                action_steps=cast(list[str], spec["action_steps"]),
                safer_alternative=cast(str | None, spec["safer_alternative"]),
                uncertainty_note=rules.uncertainty_disclaimer,
                impact_estimate_id=cast(uuid.UUID | None, spec["impact_estimate_id"]),
                evidence_document_ids=doc_ids,
                is_ai_enriched=category in enriched_categories,
                valid_until=valid_until,
                created_at=now,
            )
            rec.feedback_entries = []
            self._session.add(rec)
            created_records.append(rec)

        await self._session.commit()
        return await self._serialize_cards(created_records)

    async def submit_feedback(
        self,
        *,
        user_id: uuid.UUID,
        recommendation_id: uuid.UUID,
        payload: RecommendationFeedbackRequest,
    ) -> RecommendationFeedbackSchema:
        feedback = await self._repo.add_recommendation_feedback(
            user_id=user_id,
            recommendation_id=recommendation_id,
            status=payload.status,
            note=payload.note,
        )
        await self._session.commit()
        return RecommendationFeedbackSchema(
            id=feedback.id,
            recommendation_id=feedback.recommendation_id,
            status=payload.status,
            note=feedback.note,
            created_at=_ensure_utc(feedback.created_at),
        )

    async def generate_screened_alternatives(
        self,
        *,
        city: str | None,
        standard: AQIStandard,
        distance_km: float = 10.0,
    ) -> list[ScreenedAlternativeSchema]:
        current: CurrentAirQualitySchema | None = None
        if city is not None:
            try:
                current = await AirQualityTelemetryService(
                    self._session, self._settings
                ).get_current_air_quality(city=city, standard=standard)
            except ExternalProviderUnavailableError:
                current = None

        rules = evaluate_environmental_rules(standard=standard, current=current)
        metro_res, _ = await self._impact_service.calculate(
            TransportImpactRequest(
                distance_km=distance_km,
                baseline_mode="car_solo_petrol",
                alternative_mode="metro_rail",
                city=city,
                standard=standard,
            )
        )
        carpool_res, _ = await self._impact_service.calculate(
            TransportImpactRequest(
                distance_km=distance_km,
                baseline_mode="car_solo_petrol",
                alternative_mode="carpool_3",
                city=city,
                standard=standard,
            )
        )
        cycle_res, _ = await self._impact_service.calculate(
            TransportImpactRequest(
                distance_km=distance_km,
                baseline_mode="car_solo_petrol",
                alternative_mode="bicycle",
                city=city,
                standard=standard,
            )
        )

        cycle_safe = not rules.block_active_outdoor_commute and rules.is_available
        return build_screened_transport_alternatives(
            distance_km=distance_km,
            cycle_safe=cycle_safe,
            metro_diff_kg=metro_res.estimated_difference,
            carpool_diff_kg=carpool_res.estimated_difference,
            cycle_diff_kg=cycle_res.estimated_difference,
        )
