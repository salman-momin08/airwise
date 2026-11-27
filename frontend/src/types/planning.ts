/**
 * TypeScript DTO contracts for daily routines, recommendations, and deterministic impact estimates.
 */

import type { AQIStandard, CommuteMode } from "@/types/api";

export type ConfidenceLevel = "low" | "medium" | "high";
export type TimeBlock = "morning" | "midday" | "afternoon" | "evening" | "night";
export type EnvironmentType = "indoor" | "outdoor" | "transit";
export type RoutineStatus = "draft" | "confirmed" | "archived";

export type RecommendationCategory =
  | "routine"
  | "transport"
  | "indoor_air"
  | "household_sustainability"
  | "community";

export type RecommendationPriority = "critical" | "high" | "medium" | "low";

export type RecommendationFeedbackStatus =
  | "helpful"
  | "not_relevant"
  | "completed"
  | "dismissed";

export type ActionType =
  | "public_transit_trip"
  | "carpool_trip"
  | "work_from_home"
  | "hepa_filtration_session"
  | "appliance_load_reduction"
  | "smoke_free_cooking_ventilation";

export interface ExposureScreeningMeta {
  evaluated: boolean;
  city: string | null;
  standard: AQIStandard | null;
  aqi: number | null;
  category: string | null;
  is_stale: boolean;
  is_development_fixture: boolean;
  recommended_for_current_aqi: boolean;
  exposure_warning: string | null;
  safer_commute_fallback: string | null;
  indoor_air_measured: boolean;
}

export interface ImpactEstimate {
  id?: string | null;
  metric: string;
  baseline_value: number;
  alternative_value: number;
  estimated_difference: number;
  unit: string;
  methodology: string;
  assumptions: string[];
  source_references: string[];
  confidence: ConfidenceLevel;
  is_estimate: true;
  calculated_at: string;
  exposure_screening?: ExposureScreeningMeta | null;
}

export interface EmissionFactor {
  mode_or_region_code: string;
  category: string;
  display_label: string;
  factor_value: number;
  unit: string;
  default_occupancy: number | null;
  exposure_modifier: number | null;
  is_active_outdoor_mode: boolean;
  source_reference: string;
  effective_year: number;
}

export interface LoggedUserAction {
  id: string;
  action_type: string;
  title: string;
  quantity: number;
  unit: string;
  is_self_reported: true;
  occurred_at: string;
  impact_estimate: ImpactEstimate | null;
}

export interface ImpactSummary {
  total_logged_actions: number;
  estimated_avoided_co2e_kg: number;
  transport_avoided_co2e_kg: number;
  energy_avoided_co2e_kg: number;
  relative_exposure_reductions_count: number;
  is_estimate: true;
  methodology_disclaimer: string;
}

export interface EnvironmentalSnapshotSummary {
  city: string;
  standard: AQIStandard;
  status: "available" | "unavailable";
  aqi: number | null;
  category: string | null;
  pm25_ug_m3: number | null;
  provider: string;
  source_type: "station" | "model" | "unavailable";
  measured_at: string | null;
  is_stale: boolean;
  is_development_fixture: boolean;
  inversion_risk_flag: boolean;
  dispersion_note: string | null;
  ventilation_guidance: string;
  indoor_air_disclaimer: string;
}

export interface RoutineActivity {
  id: string;
  slot_order: number;
  time_block: TimeBlock;
  start_time: string;
  duration_minutes: number;
  title: string;
  environment_type: EnvironmentType;
  exposure_note: string;
  safer_alternative: string | null;
  explanation: string;
  safety_warning: string | null;
  impact_estimate: ImpactEstimate | null;
  confidence: ConfidenceLevel;
}

export interface RoutineActivityEditable {
  time_block: TimeBlock;
  start_time: string;
  duration_minutes: number;
  title: string;
  environment_type: EnvironmentType;
  safer_alternative?: string | null;
}

export interface DailyRoutine {
  id: string;
  location_id: string | null;
  city: string;
  plan_date: string;
  aqi_standard: AQIStandard;
  status: RoutineStatus;
  environmental_snapshot_at: string | null;
  environmental_summary: EnvironmentalSnapshotSummary | null;
  activities: RoutineActivity[];
  requires_explicit_confirmation: boolean;
  created_at: string;
  updated_at: string;
}

export interface EvidenceCitation {
  document_id: string;
  title: string;
  publisher: string;
  source_url: string;
  last_reviewed_date: string;
  freshness_note?: string | null;
}

export interface RecommendationCard {
  id: string;
  city: string;
  aqi_standard: AQIStandard;
  category: RecommendationCategory;
  priority: RecommendationPriority;
  title: string;
  reason: string;
  action_steps: string[];
  safer_alternative: string | null;
  uncertainty_note: string;
  impact_estimate: ImpactEstimate | null;
  evidence_references: EvidenceCitation[];
  is_ai_enriched: boolean;
  latest_feedback: RecommendationFeedbackStatus | null;
  valid_until: string;
  created_at: string;
}

export interface TransportComparePayload {
  calculator_type: "transport";
  distance_km: number;
  baseline_mode: CommuteMode;
  alternative_mode: CommuteMode;
  city: string;
  standard: AQIStandard;
}

export interface IndoorFiltrationPayload {
  calculator_type: "indoor_filtration";
  room_area_m2: number;
  ceiling_height_m: number;
  cadr_m3_per_hour: number;
  has_active_indoor_smoke: boolean;
}

export interface HouseholdEnergyPayload {
  calculator_type: "household_energy";
  baseline_power_kw: number;
  alternative_power_kw: number;
  operating_hours: number;
  grid_region_code: "india_cea_grid_avg" | "us_epa_egrid_avg";
}

export interface RelativeExposurePayload {
  calculator_type: "relative_exposure";
  outdoor_pm25_ug_m3: number;
  duration_hours: number;
  baseline_env_modifier: number;
  alternative_env_modifier: number;
  assumption_note: string;
}

export type ImpactCalculationPayload =
  | TransportComparePayload
  | IndoorFiltrationPayload
  | HouseholdEnergyPayload
  | RelativeExposurePayload;
