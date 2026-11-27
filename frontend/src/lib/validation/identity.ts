import { COMMUTE_MODE_VALUES } from "@/lib/constants/commute-modes";
import { z } from "zod";

const passwordPolicy = z
  .string()
  .min(10, "Password must be at least 10 characters.")
  .max(128, "Password must be at most 128 characters.")
  .refine(
    (val) => /[a-zA-Z]/.test(val) && /\d/.test(val),
    "Password must include at least one letter and one number.",
  );

export const loginSchema = z.object({
  email: z.string().trim().email("Enter a valid email address."),
  password: z.string().min(1, "Enter your password.").max(128),
});
export type LoginFormValues = z.infer<typeof loginSchema>;

export const registerSchema = z.object({
  display_name: z
    .string()
    .trim()
    .min(2, "Display name must be at least 2 characters.")
    .max(120, "Display name must be at most 120 characters."),
  email: z.string().trim().email("Enter a valid email address."),
  password: passwordPolicy,
  preferred_aqi_standard: z.enum(["india_naqi", "us_epa"]),
  timezone: z.string().min(2).max(64),
});
export type RegisterFormValues = z.infer<typeof registerSchema>;

export const forgotPasswordSchema = z.object({
  email: z.string().trim().email("Enter a valid email address."),
});
export type ForgotPasswordFormValues = z.infer<typeof forgotPasswordSchema>;

export const resetPasswordSchema = z.object({
  token: z.string().min(16, "Reset token is invalid."),
  new_password: passwordPolicy,
});
export type ResetPasswordFormValues = z.infer<typeof resetPasswordSchema>;

export const profileSettingsSchema = z.object({
  display_name: z
    .string()
    .trim()
    .min(2, "Display name must be at least 2 characters.")
    .max(120),
  preferred_aqi_standard: z.enum(["india_naqi", "us_epa"]),
  timezone: z.string().trim().min(2, "Enter a valid IANA timezone.").max(64),
  locale: z.enum(["en", "hi"]),
});
export type ProfileSettingsFormValues = z.infer<typeof profileSettingsSchema>;

export const commuteModeValues = COMMUTE_MODE_VALUES;

export const preferencesSchema = z.object({
  age_category: z
    .enum(["youth", "adult", "older_adult", "prefer_not_to_say"])
    .nullable(),
  household_size: z.number().int().min(1).max(20).nullable(),
  has_vulnerable_members: z.boolean().nullable(),
  commute_modes: z.array(z.enum(commuteModeValues)).max(10),
  cooking_type: z.string().max(64).nullable(),
  ventilation_type: z.string().max(64).nullable(),
  has_hepa_purifier: z.boolean(),
  budget_tier: z.enum(["low", "moderate", "flexible"]).nullable(),
});
export type PreferencesFormValues = z.infer<typeof preferencesSchema>;

export const savedLocationCreateSchema = z
  .object({
    label: z.enum(["home", "workplace", "school", "other"]),
    display_name: z
      .string()
      .trim()
      .min(2, "Location name must be at least 2 characters.")
      .max(160),
    city: z.string().trim().min(2, "Select or enter a city.").max(120),
    state_region: z.string().trim().max(120).optional().or(z.literal("")),
    country_code: z.string().trim().length(2, "Use a 2-letter ISO country code."),
    postal_code: z.string().trim().max(32).optional().or(z.literal("")),
    location_precision: z.enum(["city", "postal_code", "neighborhood", "exact"]),
    latitude: z.number().min(-90).max(90).nullable(),
    longitude: z.number().min(-180).max(180).nullable(),
    timezone: z.string().trim().min(2).max(64),
    is_primary: z.boolean(),
  })
  .superRefine((data, ctx) => {
    if (
      data.location_precision === "exact" &&
      (data.latitude === null || data.longitude === null)
    ) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["location_precision"],
        message:
          "Exact precision requires consented coordinates (use browser location or enter coordinates).",
      });
    }
  });
export type SavedLocationFormValues = z.infer<typeof savedLocationCreateSchema>;
