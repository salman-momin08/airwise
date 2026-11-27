/**
 * Canonical transport mode options and labels shared across commute calculators and preferences.
 */

import type { CommuteMode } from "@/types/api";

export const COMMUTE_MODE_VALUES = [
  "walk",
  "bicycle",
  "two_wheeler_petrol",
  "two_wheeler_ev",
  "car_solo_petrol",
  "car_ev",
  "carpool_3",
  "bus",
  "metro_rail",
  "work_from_home",
] as const;

export const COMMUTE_MODE_OPTIONS: ReadonlyArray<{
  value: CommuteMode;
  label: string;
}> = [
  { value: "car_solo_petrol", label: "Solo Petrol Car" },
  { value: "metro_rail", label: "Urban Metro / Suburban Rail" },
  { value: "bus", label: "Public City Bus" },
  { value: "carpool_3", label: "Shared Carpool (3 Occupants)" },
  { value: "car_ev", label: "Electric Car" },
  { value: "two_wheeler_petrol", label: "Petrol Two-Wheeler" },
  { value: "two_wheeler_ev", label: "Electric Two-Wheeler" },
  { value: "bicycle", label: "Bicycle" },
  { value: "walk", label: "Walking" },
  { value: "work_from_home", label: "Work from Home" },
];
