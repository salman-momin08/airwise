import { z } from "zod";

const commuteModeEnum = z.enum([
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
]);

const aqiStandardEnum = z.enum(["india_naqi", "us_epa"]);

export const transportCompareFormSchema = z.object({
  city: z.string().trim().min(2, "Enter a city name.").max(100),
  standard: aqiStandardEnum,
  distance_km: z.coerce.number().min(0.5, "Enter at least 0.5 km.").max(2000),
  baseline_mode: commuteModeEnum,
  alternative_mode: commuteModeEnum,
});

export type TransportCompareFormValues = z.infer<typeof transportCompareFormSchema>;

export const indoorFiltrationFormSchema = z.object({
  room_area_m2: z.coerce.number().min(2, "Room area must be at least 2 m².").max(500),
  ceiling_height_m: z.coerce.number().min(1.8, "Ceiling height must be at least 1.8 m.").max(10),
  cadr_m3_per_hour: z.coerce.number().min(10, "Enter a CADR >= 10 m³/h.").max(3000),
  has_active_indoor_smoke: z.boolean(),
});

export type IndoorFiltrationFormValues = z.infer<typeof indoorFiltrationFormSchema>;

export const householdEnergyFormSchema = z.object({
  baseline_power_kw: z.coerce.number().min(0.05, "Baseline power must be >= 0.05 kW.").max(100),
  alternative_power_kw: z.coerce.number().min(0, "Alternative power must be >= 0 kW.").max(100),
  operating_hours: z.coerce.number().min(0.25, "Operating hours must be >= 0.25 h.").max(744),
  grid_region_code: z.enum(["india_cea_grid_avg", "us_epa_egrid_avg"]),
});

export type HouseholdEnergyFormValues = z.infer<typeof householdEnergyFormSchema>;

export const logActionFormSchema = z.object({
  action_type: z.enum([
    "public_transit_trip",
    "carpool_trip",
    "work_from_home",
    "hepa_filtration_session",
    "appliance_load_reduction",
    "smoke_free_cooking_ventilation",
  ]),
  title: z.string().trim().min(3, "Describe the completed action (at least 3 characters).").max(200),
  quantity: z.coerce.number().gt(0, "Quantity must be positive.").max(10000),
  unit: z.string().trim().min(1, "Enter a unit (e.g., km, hours, sessions).").max(32),
});

export type LogActionFormValues = z.infer<typeof logActionFormSchema>;

export const generateRoutineFormSchema = z.object({
  city: z.string().trim().min(2, "Enter a city name.").max(100),
  standard: aqiStandardEnum,
  commute_distance_km: z.coerce.number().min(0, "Distance cannot be negative.").max(200),
});

export type GenerateRoutineFormValues = z.infer<typeof generateRoutineFormSchema>;
