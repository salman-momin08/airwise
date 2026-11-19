from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_response_meta
from app.schemas.common import ApiResponse, ResponseMeta
from app.schemas.impact import ImpactEstimateSchema, TransportImpactRequest
from app.services.impact.calculators import calculate_transport_emissions

router = APIRouter(prefix="/impact", tags=["impact"])


@router.post("/calculate", response_model=ApiResponse[ImpactEstimateSchema])
async def calculate_transport_impact_endpoint(
    payload: TransportImpactRequest,
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
) -> ApiResponse[ImpactEstimateSchema]:
    result = calculate_transport_emissions(
        distance_km=payload.distance_km,
        baseline_vkm_factor_kg_co2e=payload.baseline_vkm_factor_kg_co2e,
        baseline_occupancy=payload.baseline_occupancy,
        alternative_vkm_factor_kg_co2e=payload.alternative_vkm_factor_kg_co2e,
        alternative_occupancy=payload.alternative_occupancy,
        factor_source_reference=payload.factor_source_reference,
    )
    return ApiResponse(data=ImpactEstimateSchema(**asdict(result)), meta=meta)
