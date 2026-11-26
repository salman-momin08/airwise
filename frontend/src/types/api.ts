export type AQIStandard = "india_naqi" | "us_epa";

export type PollutantCode = "pm25" | "pm10" | "no2" | "so2" | "co" | "o3";

export type LocationLabel = "home" | "workplace" | "school" | "other";

export type LocationPrecision = "city" | "postal_code" | "neighborhood" | "exact";

export type AgeCategory = "youth" | "adult" | "older_adult" | "prefer_not_to_say";

export type BudgetTier = "low" | "moderate" | "flexible";

export type CommuteMode =
  | "walk"
  | "bicycle"
  | "two_wheeler_petrol"
  | "two_wheeler_ev"
  | "car_solo_petrol"
  | "car_ev"
  | "carpool_3"
  | "bus"
  | "metro_rail"
  | "work_from_home";

export interface AuthPrincipal {
  user_id: string | null;
  email?: string | null;
  display_name?: string | null;
  role: "guest" | "user" | "moderator" | "admin";
  is_email_verified: boolean;
  preferred_aqi_standard: AQIStandard;
  session_id?: string | null;
}

export interface SessionRecord {
  id: string;
  user_agent: string | null;
  created_at: string;
  expires_at: string;
  is_current: boolean;
}

export interface TimeWindowSchedule {
  start_time: string;
  end_time: string;
  days: string[];
}

export interface UserProfile {
  display_name: string;
  locale: string;
  preferred_aqi_standard: AQIStandard;
  timezone: string;
  updated_at: string;
}

export interface UserPreferences {
  age_category: AgeCategory | null;
  household_size: number | null;
  has_vulnerable_members: boolean | null;
  work_schedule: TimeWindowSchedule | null;
  school_schedule: TimeWindowSchedule | null;
  commute_modes: CommuteMode[];
  cooking_type: string | null;
  ventilation_type: string | null;
  has_hepa_purifier: boolean;
  budget_tier: BudgetTier | null;
  sustainability_goals: string[];
  save_chat_history: boolean;
  consent_updated_at: string | null;
}

export interface UserMe {
  id: string;
  email: string;
  role: string;
  is_email_verified: boolean;
  created_at: string;
  profile: UserProfile;
  preferences: UserPreferences;
}

export interface SavedLocation {
  id: string;
  label: LocationLabel;
  display_name: string;
  city: string;
  state_region: string | null;
  country_code: string;
  postal_code: string | null;
  latitude: number | null;
  longitude: number | null;
  location_precision: LocationPrecision;
  timezone: string;
  is_primary: boolean;
  created_at: string;
}

export interface GazetteerMatch {
  city: string;
  state_region: string;
  country_code: string;
  postal_prefix: string;
  timezone: string;
}

export interface AccountExportBundle {
  exported_at: string;
  schema_version: string;
  account: UserMe;
  saved_locations: SavedLocation[];
  active_sessions_count: number;
  chat_history: Array<{
    conversation_id: string;
    id: string;
    role: "user" | "assistant";
    content: string;
    structured_response: unknown;
    created_at: string;
  }>;
  daily_routines?: unknown[];
  recommendations?: unknown[];
  logged_actions?: unknown[];
}

export interface ResponseMeta {
  request_id: string;
  timestamp: string;
  pagination?: {
    cursor: string | null;
    has_more: boolean;
    limit: number;
  } | null;
}

export interface ApiResponse<T> {
  data: T;
  meta: ResponseMeta;
}

export interface ApiErrorEnvelope {
  error: {
    code: string;
    message: string;
    request_id: string;
  };
}

export interface PollutantReading {
  pollutant: PollutantCode;
  concentration: number;
  unit: string;
  averaging_period_hours: number;
  sub_index: number | null;
}

export interface CurrentAirQuality {
  city: string;
  location_precision: "city" | "postal_code" | "neighborhood" | "exact";
  standard: AQIStandard;
  status: "available" | "unavailable";
  aqi: number | null;
  category: string | null;
  dominant_pollutant: PollutantCode | null;
  pollutants: PollutantReading[];
  measured_at: string | null;
  provider: string;
  source_type: "station" | "model" | "unavailable";
  is_stale: boolean;
  is_development_fixture: boolean;
  precaution_summary: string;
  unavailable_reason: string | null;
}

export type HistoryPeriod = "24h" | "7d" | "30d";

export interface HistoricalAirQualityPoint {
  timestamp: string;
  aqi: number | null;
  category: string | null;
  pm25_ug_m3: number | null;
  pm10_ug_m3: number | null;
  dominant_pollutant: PollutantCode | null;
}

export interface HistoricalAirQuality {
  city: string;
  standard: AQIStandard;
  period: HistoryPeriod;
  provider: string;
  source_type: "station" | "model" | "unavailable";
  is_stale: boolean;
  is_development_fixture: boolean;
  series: HistoricalAirQualityPoint[];
}

export interface ForecastPoint {
  forecast_for: string;
  aqi: number | null;
  category: string | null;
  dominant_pollutant: PollutantCode | null;
  pm25_ug_m3: number | null;
  pm10_ug_m3: number | null;
  confidence_level: "low" | "medium" | "high";
  safer_outdoor_window: boolean;
}

export interface AirQualityForecast {
  city: string;
  standard: AQIStandard;
  generated_at: string;
  provider: string;
  source_type: "station" | "model" | "unavailable";
  is_stale: boolean;
  is_development_fixture: boolean;
  points: ForecastPoint[];
}

export interface MonitoringStation {
  station_id: string;
  name: string;
  city: string;
  state_region: string | null;
  country_code: string;
  latitude: number;
  longitude: number;
  distance_km: number | null;
  provider: string;
  source_type: "station" | "model";
  standard: AQIStandard;
  aqi: number | null;
  category: string | null;
  dominant_pollutant: PollutantCode | null;
  measured_at: string | null;
  is_stale: boolean;
  is_development_fixture: boolean;
}

export interface StationGeoJsonFeature {
  type: "Feature";
  geometry: {
    type: "Point";
    coordinates: [number, number];
  };
  properties: {
    station_id: string;
    name: string;
    city: string;
    provider: string;
    source_type: "station" | "model";
    standard: AQIStandard;
    aqi: number | null;
    category: string | null;
    dominant_pollutant: PollutantCode | null;
    measured_at: string | null;
    is_stale: boolean;
    is_development_fixture: boolean;
  };
}

export interface StationGeoJsonCollection {
  type: "FeatureCollection";
  standard: AQIStandard;
  is_development_fixture: boolean;
  features: StationGeoJsonFeature[];
}

export interface CurrentWeather {
  city: string;
  temperature_c: number;
  humidity_pct: number;
  wind_speed_mps: number;
  wind_direction_deg: number | null;
  inversion_risk_flag: boolean | null;
  dispersion_note: string;
  observed_at: string;
  provider: string;
  is_stale: boolean;
  is_development_fixture: boolean;
}

export interface ImpactEstimate {
  metric: string;
  baseline_value: number;
  alternative_value: number;
  estimated_difference: number;
  unit: string;
  methodology: string;
  assumptions: string[];
  source_references: string[];
  confidence: "low" | "medium" | "high";
  is_estimate: true;
  calculated_at: string;
}
