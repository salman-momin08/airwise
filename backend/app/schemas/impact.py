from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TransportImpactRequest(BaseModel):
    distance_km: float = Field(ge=0, le=2000)
    baseline_vkm_factor_kg_co2e: float = Field(ge=0, le=5.0)
    baseline_occupancy: float = Field(gt=0, le=200)
    alternative_vkm_factor_kg_co2e: float = Field(ge=0, le=5.0)
    alternative_occupancy: float = Field(gt=0, le=200)
    factor_source_reference: str = Field(
        default="IPCC / India GHG Program Passenger Transport Emission Factors",
        min_length=3,
    )


class ImpactEstimateSchema(BaseModel):
    metric: str
    baseline_value: float
    alternative_value: float
    estimated_difference: float
    unit: str
    methodology: str
    assumptions: list[str]
    source_references: list[str]
    confidence: Literal["low", "medium", "high"]
    is_estimate: Literal[True] = True
    calculated_at: str
