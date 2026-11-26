"""Reference emission factors and metadata seeder entrypoint."""

from __future__ import annotations

import asyncio

from app.db.session import get_session_factory
from app.repositories.planning_repository import PlanningRepository
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


async def seed_emission_factors() -> int:
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
        await session.commit()
    return len(REFERENCE_EMISSION_FACTORS)


def main() -> None:
    seeded = asyncio.run(seed_emission_factors())
    print(f"Seeded {seeded} verified reference emission factors.")


if __name__ == "__main__":
    main()
