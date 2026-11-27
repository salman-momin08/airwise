from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.identity import CommuteModeLiteral
from app.services.air_quality.aqi_calculator import AQIStandard

ActionTypeLiteral = Literal[
    "public_transit_trip",
    "carpool_trip",
    "work_from_home",
    "hepa_filtration_session",
    "appliance_load_reduction",
    "smoke_free_cooking_ventilation",
]

class TransportImpactRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calculator_type: Literal["transport"] = "transport"
    distance_km: float = Field(ge=0, le=2000)
    baseline_mode: CommuteModeLiteral | None = None
    alternative_mode: CommuteModeLiteral | None = None
    baseline_vkm_factor_kg_co2e: float | None = Field(default=None, ge=0, le=5.0)
    baseline_occupancy: float | None = Field(default=None, gt=0, le=200)
    alternative_vkm_factor_kg_co2e: float | None = Field(default=None, ge=0, le=5.0)
    alternative_occupancy: float | None = Field(default=None, gt=0, le=200)
    factor_source_reference: str = Field(
        default="IPCC / India GHG Program Passenger Transport Emission Factors",
        min_length=3,
        max_length=300,
    )
    city: str | None = Field(default=None, min_length=2, max_length=100, pattern=r"^[\w .'-]+$")
    standard: AQIStandard = AQIStandard.INDIA_NAQI

    @model_validator(mode="after")
    def validate_mode_or_explicit_factors(self) -> TransportImpactRequest:
        has_modes = self.baseline_mode is not None and self.alternative_mode is not None
        has_factors = (
            self.baseline_vkm_factor_kg_co2e is not None
            and self.baseline_occupancy is not None
            and self.alternative_vkm_factor_kg_co2e is not None
            and self.alternative_occupancy is not None
        )
        if not (has_modes or has_factors):
            raise ValueError(
                "Provide either (baseline_mode, alternative_mode) or explicit "
                "(vkm_factor_kg_co2e, occupancy) pairs for both baseline and alternative."
            )
        return self

class HouseholdEnergyImpactRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calculator_type: Literal["household_energy"]
    baseline_power_kw: float = Field(ge=0, le=100)
    alternative_power_kw: float = Field(ge=0, le=100)
    operating_hours: float = Field(ge=0, le=744)
    grid_region_code: Literal["india_cea_grid_avg", "us_epa_egrid_avg"] | None = None
    grid_emission_factor_kg_per_kwh: float | None = Field(default=None, ge=0, le=3.0)
    grid_source_reference: str = Field(
        default="Central Electricity Authority (CEA) CO2 Baseline Database v19 (2024)",
        min_length=3,
        max_length=300,
    )

    @model_validator(mode="after")
    def validate_grid_source(self) -> HouseholdEnergyImpactRequest:
        if self.grid_region_code is None and self.grid_emission_factor_kg_per_kwh is None:
            self.grid_region_code = "india_cea_grid_avg"
        return self

class IndoorFiltrationImpactRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calculator_type: Literal["indoor_filtration"]
    room_area_m2: float = Field(gt=0, le=500)
    ceiling_height_m: float = Field(gt=0, le=10)
    cadr_m3_per_hour: float = Field(ge=0, le=3000)
    infiltration_ach: float = Field(default=0.6, ge=0, le=5.0)
    penetration_factor: float = Field(default=0.8, ge=0, le=1.0)
    deposition_rate_per_hour: float = Field(default=0.2, ge=0, le=5.0)
    has_active_indoor_smoke: bool = False

class RelativeExposureImpactRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calculator_type: Literal["relative_exposure"]
    outdoor_pm25_ug_m3: float = Field(ge=0, le=2000)
    duration_hours: float = Field(ge=0, le=24)
    baseline_env_modifier: float = Field(ge=0, le=5.0)
    alternative_env_modifier: float = Field(ge=0, le=5.0)
    assumption_note: str = Field(
        default="Enclosed filtered microenvironment vs unfiltered roadside exposure",
        min_length=3,
        max_length=300,
    )

ImpactCalculationRequest = Annotated[
    TransportImpactRequest
    | HouseholdEnergyImpactRequest
    | IndoorFiltrationImpactRequest
    | RelativeExposureImpactRequest,
    Field(discriminator="calculator_type"),
]

class ExposureScreeningMetaSchema(BaseModel):
    evaluated: bool = False
    city: str | None = None
    standard: AQIStandard | None = None
    aqi: int | None = None
    category: str | None = None
    is_stale: bool = False
    is_development_fixture: bool = False
    recommended_for_current_aqi: bool = True
    exposure_warning: str | None = None
    safer_commute_fallback: str | None = None
    indoor_air_measured: bool = False

class ImpactEstimateSchema(BaseModel):
    id: UUID | None = None
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
    exposure_screening: ExposureScreeningMetaSchema | None = None

class EmissionFactorSchema(BaseModel):
    mode_or_region_code: str
    category: str
    display_label: str
    factor_value: float
    unit: str
    default_occupancy: float | None
    exposure_modifier: float | None
    is_active_outdoor_mode: bool = False
    source_reference: str
    effective_year: int

class LogUserActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    action_type: ActionTypeLiteral
    title: str = Field(min_length=3, max_length=200)
    quantity: float = Field(gt=0, le=10000)
    unit: str = Field(min_length=1, max_length=32)
    occurred_at: datetime | None = None
    calculation: ImpactCalculationRequest | None = None

class LoggedUserActionSchema(BaseModel):
    id: UUID
    action_type: str
    title: str
    quantity: float
    unit: str
    is_self_reported: Literal[True] = True
    occurred_at: datetime
    impact_estimate: ImpactEstimateSchema | None = None

class ImpactSummarySchema(BaseModel):
    total_logged_actions: int
    estimated_avoided_co2e_kg: float
    transport_avoided_co2e_kg: float
    energy_avoided_co2e_kg: float
    relative_exposure_reductions_count: int
    is_estimate: Literal[True] = True
    methodology_disclaimer: str = (
        "All avoided CO2e and relative exposure figures are deterministic estimates based on "
        "self-reported actions and reference emission factors—never ambient AQI reductions."
    )
