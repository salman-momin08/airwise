from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ResourceNotFoundError
from app.models.planning import (
    DailyRoutine,
    EmissionFactor,
    ImpactEstimate,
    Recommendation,
    RecommendationFeedback,
    RoutineActivity,
    UserAction,
)


class PlanningRepository:
    """Async SQLAlchemy 2.x repository enforcing strict object-level user_id ownership."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_emission_factors(
        self, *, category: str | None = None
    ) -> list[EmissionFactor]:
        stmt = select(EmissionFactor).where(EmissionFactor.is_active.is_(True))
        if category is not None:
            stmt = stmt.where(EmissionFactor.category == category)
        stmt = stmt.order_by(EmissionFactor.category, EmissionFactor.mode_or_region_code)
        result = await self._session.scalars(stmt)
        return list(result.all())

    async def get_emission_factor_by_code(self, code: str) -> EmissionFactor | None:
        return await self._session.scalar(
            select(EmissionFactor).where(
                EmissionFactor.mode_or_region_code == code,
                EmissionFactor.is_active.is_(True),
            )
        )

    async def upsert_emission_factor(
        self,
        *,
        category: str,
        mode_or_region_code: str,
        display_label: str,
        factor_value: float,
        unit: str,
        default_occupancy: float | None,
        exposure_modifier: float | None,
        source_reference: str,
        effective_year: int,
    ) -> EmissionFactor:
        existing = await self._session.scalar(
            select(EmissionFactor).where(
                EmissionFactor.mode_or_region_code == mode_or_region_code
            )
        )
        if existing is None:
            existing = EmissionFactor(
                id=uuid.uuid4(),
                category=category,
                mode_or_region_code=mode_or_region_code,
                display_label=display_label,
                factor_value=factor_value,
                unit=unit,
                default_occupancy=default_occupancy,
                exposure_modifier=exposure_modifier,
                source_reference=source_reference,
                effective_year=effective_year,
                is_active=True,
            )
            self._session.add(existing)
        else:
            existing.category = category
            existing.display_label = display_label
            existing.factor_value = factor_value
            existing.unit = unit
            existing.default_occupancy = default_occupancy
            existing.exposure_modifier = exposure_modifier
            existing.source_reference = source_reference
            existing.effective_year = effective_year
            existing.is_active = True
        return existing

    async def create_impact_estimate(
        self,
        *,
        user_id: uuid.UUID | None,
        user_action_id: uuid.UUID | None,
        metric: str,
        baseline_value: float,
        alternative_value: float,
        estimated_difference: float,
        unit: str,
        methodology: str,
        assumptions: list[str],
        source_references: list[str],
        confidence: str,
        calculated_at: datetime,
    ) -> ImpactEstimate:
        record = ImpactEstimate(
            id=uuid.uuid4(),
            user_id=user_id,
            user_action_id=user_action_id,
            metric=metric,
            baseline_value=baseline_value,
            alternative_value=alternative_value,
            estimated_difference=estimated_difference,
            unit=unit,
            methodology=methodology,
            assumptions=assumptions,
            source_references=source_references,
            confidence=confidence,
            is_estimate=True,
            calculated_at=calculated_at,
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def get_impact_estimates_by_ids(
        self, estimate_ids: set[uuid.UUID]
    ) -> dict[uuid.UUID, ImpactEstimate]:
        if not estimate_ids:
            return {}
        rows = await self._session.scalars(
            select(ImpactEstimate).where(ImpactEstimate.id.in_(estimate_ids))
        )
        return {row.id: row for row in rows}

    async def create_user_action(
        self,
        *,
        user_id: uuid.UUID,
        action_type: str,
        title: str,
        quantity: float,
        unit: str,
        occurred_at: datetime,
    ) -> UserAction:
        record = UserAction(
            id=uuid.uuid4(),
            user_id=user_id,
            action_type=action_type,
            title=title,
            quantity=quantity,
            unit=unit,
            occurred_at=occurred_at,
            is_self_reported=True,
            created_at=datetime.now(tz=UTC),
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def list_user_actions(
        self, *, user_id: uuid.UUID, limit: int = 100
    ) -> list[UserAction]:
        stmt = (
            select(UserAction)
            .options(selectinload(UserAction.estimates))
            .where(UserAction.user_id == user_id)
            .order_by(UserAction.occurred_at.desc(), UserAction.created_at.desc())
            .limit(limit)
        )
        rows = await self._session.scalars(stmt)
        return list(rows.all())

    async def list_user_impact_estimates(
        self, *, user_id: uuid.UUID, limit: int = 200
    ) -> list[ImpactEstimate]:
        stmt = (
            select(ImpactEstimate)
            .where(ImpactEstimate.user_id == user_id)
            .order_by(ImpactEstimate.calculated_at.desc())
            .limit(limit)
        )
        rows = await self._session.scalars(stmt)
        return list(rows.all())

    async def list_routines(
        self, *, user_id: uuid.UUID, limit: int = 30
    ) -> list[DailyRoutine]:
        stmt = (
            select(DailyRoutine)
            .options(selectinload(DailyRoutine.activities))
            .where(DailyRoutine.user_id == user_id)
            .order_by(DailyRoutine.plan_date.desc(), DailyRoutine.updated_at.desc())
            .limit(limit)
        )
        rows = await self._session.scalars(stmt)
        return list(rows.all())

    async def require_routine(
        self, *, user_id: uuid.UUID, routine_id: uuid.UUID
    ) -> DailyRoutine:
        routine = await self._session.scalar(
            select(DailyRoutine)
            .execution_options(populate_existing=True)
            .options(selectinload(DailyRoutine.activities))
            .where(DailyRoutine.id == routine_id, DailyRoutine.user_id == user_id)
        )
        if routine is None:
            raise ResourceNotFoundError("Daily routine was not found.")
        return routine

    async def replace_routine_activities(
        self,
        *,
        routine: DailyRoutine,
        activities: list[RoutineActivity],
    ) -> None:
        await self._session.execute(
            delete(RoutineActivity).where(RoutineActivity.routine_id == routine.id)
        )
        for item in activities:
            self._session.add(item)
        routine.updated_at = datetime.now(tz=UTC)
        await self._session.flush()
        await self._session.refresh(routine, attribute_names=["activities"])

    async def delete_routine(self, *, user_id: uuid.UUID, routine_id: uuid.UUID) -> None:
        routine = await self.require_routine(user_id=user_id, routine_id=routine_id)
        await self._session.execute(
            delete(RoutineActivity).where(RoutineActivity.routine_id == routine.id)
        )
        await self._session.execute(
            delete(DailyRoutine).where(
                DailyRoutine.id == routine.id, DailyRoutine.user_id == user_id
            )
        )

    async def list_active_recommendations(
        self, *, user_id: uuid.UUID, now: datetime
    ) -> list[Recommendation]:
        stmt = (
            select(Recommendation)
            .options(selectinload(Recommendation.feedback_entries))
            .where(
                Recommendation.user_id == user_id,
                Recommendation.valid_until > now,
            )
            .order_by(Recommendation.created_at.desc(), Recommendation.id)
        )
        rows = await self._session.scalars(stmt)
        return list(rows.all())

    async def expire_active_recommendations_for_city(
        self, *, user_id: uuid.UUID, city: str, now: datetime
    ) -> None:
        active = await self._session.scalars(
            select(Recommendation).where(
                Recommendation.user_id == user_id,
                Recommendation.city == city,
                Recommendation.valid_until > now,
            )
        )
        for rec in active:
            rec.valid_until = now

    async def require_recommendation(
        self, *, user_id: uuid.UUID, recommendation_id: uuid.UUID
    ) -> Recommendation:
        rec = await self._session.scalar(
            select(Recommendation)
            .options(selectinload(Recommendation.feedback_entries))
            .where(
                Recommendation.id == recommendation_id,
                Recommendation.user_id == user_id,
            )
        )
        if rec is None:
            raise ResourceNotFoundError("Recommendation was not found.")
        return rec

    async def add_recommendation_feedback(
        self,
        *,
        user_id: uuid.UUID,
        recommendation_id: uuid.UUID,
        status: str,
        note: str | None,
    ) -> RecommendationFeedback:
        await self.require_recommendation(
            user_id=user_id, recommendation_id=recommendation_id
        )
        feedback = RecommendationFeedback(
            id=uuid.uuid4(),
            recommendation_id=recommendation_id,
            user_id=user_id,
            status=status,
            note=note,
            created_at=datetime.now(tz=UTC),
        )
        self._session.add(feedback)
        await self._session.flush()
        return feedback

    async def erase_user_data(self, *, user_id: uuid.UUID) -> None:
        user_recs = select(Recommendation.id).where(Recommendation.user_id == user_id)
        await self._session.execute(
            delete(RecommendationFeedback).where(
                or_(
                    RecommendationFeedback.user_id == user_id,
                    RecommendationFeedback.recommendation_id.in_(user_recs),
                )
            )
        )
        await self._session.execute(
            delete(Recommendation).where(Recommendation.user_id == user_id)
        )
        user_routines = select(DailyRoutine.id).where(DailyRoutine.user_id == user_id)
        await self._session.execute(
            delete(RoutineActivity).where(RoutineActivity.routine_id.in_(user_routines))
        )
        await self._session.execute(
            delete(DailyRoutine).where(DailyRoutine.user_id == user_id)
        )
        user_actions = select(UserAction.id).where(UserAction.user_id == user_id)
        await self._session.execute(
            delete(ImpactEstimate).where(
                or_(
                    ImpactEstimate.user_id == user_id,
                    ImpactEstimate.user_action_id.in_(user_actions),
                )
            )
        )
        await self._session.execute(
            delete(UserAction).where(UserAction.user_id == user_id)
        )

    async def export_user_data(
        self, *, user_id: uuid.UUID
    ) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
        routines = await self.list_routines(user_id=user_id, limit=500)
        routine_items: list[dict[str, object]] = [
            {
                "id": str(r.id),
                "city": r.city,
                "plan_date": r.plan_date.isoformat(),
                "aqi_standard": r.aqi_standard,
                "status": r.status,
                "activities": [
                    {
                        "time_block": a.time_block,
                        "start_time": a.start_time.strftime("%H:%M"),
                        "duration_minutes": a.duration_minutes,
                        "title": a.title,
                        "environment_type": a.environment_type,
                    }
                    for a in r.activities
                ],
                "created_at": r.created_at.isoformat(),
            }
            for r in routines
        ]
        recs = await self._session.scalars(
            select(Recommendation)
            .where(Recommendation.user_id == user_id)
            .order_by(Recommendation.created_at.desc())
        )
        rec_items: list[dict[str, object]] = [
            {
                "id": str(rec.id),
                "city": rec.city,
                "category": rec.category,
                "priority": rec.priority,
                "title": rec.title,
                "created_at": rec.created_at.isoformat(),
            }
            for rec in recs
        ]
        actions = await self.list_user_actions(user_id=user_id, limit=1000)
        action_items: list[dict[str, object]] = [
            {
                "id": str(act.id),
                "action_type": act.action_type,
                "title": act.title,
                "quantity": act.quantity,
                "unit": act.unit,
                "is_self_reported": act.is_self_reported,
                "occurred_at": act.occurred_at.isoformat(),
            }
            for act in actions
        ]
        return routine_items, rec_items, action_items
