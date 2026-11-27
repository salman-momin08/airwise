import { z } from "zod";

const hhmmRegex = /^(?:[01]\d|2[0-3]):[0-5]\d$/;

export const createAlertRuleFormSchema = z
  .object({
    city: z.string().trim().min(2, "Enter a city name.").max(100),
    alert_type: z.enum([
      "aqi_threshold",
      "severe_smog_episode",
      "forecast_deterioration",
      "clean_air_window",
      "stale_telemetry_warning",
      "daily_digest",
    ]),
    aqi_standard: z.enum(["india_naqi", "us_epa"]),
    threshold_value: z.coerce.number<number>().int().min(10).max(500),
    enable_email: z.boolean(),
    enable_quiet_hours: z.boolean(),
    quiet_hours_start: z.string().regex(hhmmRegex, "Use HH:MM (24-hour) format."),
    quiet_hours_end: z.string().regex(hhmmRegex, "Use HH:MM (24-hour) format."),
    cooldown_minutes: z.coerce.number<number>().int().min(15).max(1440),
    timezone: z.string().trim().min(2, "Enter an IANA timezone.").max(64),
  })
  .refine(
    (vals) => !vals.enable_quiet_hours || vals.quiet_hours_start !== vals.quiet_hours_end,
    {
      message: "Quiet hours start and end times must differ.",
      path: ["quiet_hours_end"],
    },
  );

export type CreateAlertRuleFormValues = z.infer<typeof createAlertRuleFormSchema>;

export const logCommunityParticipationFormSchema = z.object({
  self_reported_actions_count: z.coerce.number<number>().int().min(1).max(50),
  commute_distance_saved_km: z.coerce.number<number>().min(0).max(500),
  note: z
    .string()
    .trim()
    .max(280)
    .refine(
      (val) =>
        !val ||
        !/[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}|\b(?:house|flat|apt|apartment|plot)\s*(?:no\.?|#)?\s*\d+\b/i.test(
          val,
        ),
      "Do not include street/unit addresses or email addresses in public notes.",
    ),
});

export type LogCommunityParticipationFormValues = z.infer<
  typeof logCommunityParticipationFormSchema
>;

export const createAbuseReportFormSchema = z.object({
  reason_category: z.enum([
    "pii_exposure",
    "misinformation",
    "unsafe_health_advice",
    "harassment_or_spam",
  ]),
  details: z
    .string()
    .trim()
    .min(8, "Provide at least 8 characters describing the issue.")
    .max(500),
});

export type CreateAbuseReportFormValues = z.infer<typeof createAbuseReportFormSchema>;

export const createCommunityFormSchema = z.object({
  slug: z
    .string()
    .trim()
    .min(3)
    .max(96)
    .regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, "Use lowercase kebab-case (e.g., south-delhi-clean-air)."),
  name: z.string().trim().min(3).max(160),
  city: z.string().trim().min(2).max(120),
  coarse_boundary_label: z.string().trim().min(3).max(160),
  description: z.string().trim().min(10).max(1200),
});

export type CreateCommunityFormValues = z.infer<typeof createCommunityFormSchema>;
