"""Reference emission factors and metadata seeder entrypoint."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db.session import get_session_factory
from app.models.community_alerts import Community, CommunityInitiative
from app.models.telemetry import AirQualitySource
from app.repositories.planning_repository import PlanningRepository
from app.services.admin.admin_service import DEFAULT_SOURCE_CATALOG
from app.services.impact.reference_factors import REFERENCE_EMISSION_FACTORS

REFERENCE_TRANSPORT_EMISSION_FACTORS: tuple[dict[str, object], ...] = tuple(
    {
        "mode_or_region_code": spec.mode_or_region_code,
        "factor_value": spec.factor_value,
        "unit": spec.unit,
        "default_occupancy": spec.default_occupancy,
        "source_reference": spec.source_reference,
        "effective_year": spec.effective_year,
    }
    for spec in REFERENCE_EMISSION_FACTORS
    if spec.category == "transport"
)

STARTER_NEIGHBORHOOD_COMMUNITIES: tuple[dict[str, str], ...] = (
    {
        "slug": "delhi-metro-clean-commute",
        "name": "Delhi Metro & School Clean-Air Circle",
        "city": "Delhi",
        "coarse_boundary_label": "Central & South Delhi · Metro Corridor",
        "description": "Voluntary rail commute buddies and school-gate no-idling pledges.",
        "initiative_title": "Winter School-Gate No-Idling Week",
        "challenge_type": "no_idling_school_week",
    },
    {
        "slug": "bengaluru-east-transit-circle",
        "name": "East Bengaluru Clean Transit Circle",
        "city": "Bengaluru",
        "coarse_boundary_label": "Indiranagar & Metro Purple Line Corridor",
        "description": "Shared carpool corridors and metro commuter challenges.",
        "initiative_title": "Purple Line Public Transit Challenge",
        "challenge_type": "public_transit_challenge",
    },
)

async def seed_emission_factors() -> int:
    now = datetime.now(tz=UTC)
    async with get_session_factory()() as session:
        repo = PlanningRepository(session)
        for spec in REFERENCE_EMISSION_FACTORS:
            await repo.upsert_emission_factor(
                category=spec.category,
                mode_or_region_code=spec.mode_or_region_code,
                display_label=spec.display_label,
                factor_value=spec.factor_value,
                unit=spec.unit,
                default_occupancy=spec.default_occupancy,
                exposure_modifier=spec.exposure_modifier,
                source_reference=spec.source_reference,
                effective_year=spec.effective_year,
            )

        for src in DEFAULT_SOURCE_CATALOG:
            existing_src = await session.scalar(
                select(AirQualitySource).where(AirQualitySource.slug == str(src["slug"]))
            )
            if existing_src is None:
                session.add(
                    AirQualitySource(
                        id=uuid.uuid4(),
                        slug=str(src["slug"]),
                        name=str(src["name"]),
                        provider_type=str(src["provider_type"]),
                        license_note=str(src["license_note"]),
                        refresh_interval_seconds=int(str(src["refresh_interval_seconds"])),
                        is_enabled=True,
                        priority_rank=int(str(src["priority_rank"])),
                    )
                )

        for comm_spec in STARTER_NEIGHBORHOOD_COMMUNITIES:
            existing_comm = await session.scalar(
                select(Community).where(Community.slug == comm_spec["slug"])
            )
            if existing_comm is None:
                comm = Community(
                    id=uuid.uuid4(),
                    slug=comm_spec["slug"],
                    name=comm_spec["name"],
                    city=comm_spec["city"],
                    coarse_boundary_label=comm_spec["coarse_boundary_label"],
                    description=comm_spec["description"],
                    moderation_policy=(
                        "Coarse neighborhood boundaries only; no street addresses, exact GPS "
                        "coordinates, unconsented names, or unsupported medical/AQI claims."
                    ),
                    created_by=None,
                    created_at=now,
                )
                session.add(comm)
                await session.flush()
                session.add(
                    CommunityInitiative(
                        id=uuid.uuid4(),
                        community_id=comm.id,
                        title=comm_spec["initiative_title"],
                        description=comm_spec["description"],
                        challenge_type=comm_spec["challenge_type"],
                        starts_at=now - timedelta(days=1),
                        ends_at=now + timedelta(days=30),
                        moderation_status="active",
                        created_by=None,
                        created_at=now,
                    )
                )

        await session.commit()
    return len(REFERENCE_EMISSION_FACTORS)

def main() -> None:
    seeded = asyncio.run(seed_emission_factors())
    print(f"Seeded {seeded} verified reference emission factors.")

if __name__ == "__main__":
    main()
