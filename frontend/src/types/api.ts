export type AQIStandard = "india_naqi" | "us_epa";

export type PollutantCode = "pm25" | "pm10" | "no2" | "so2" | "co" | "o3";

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
