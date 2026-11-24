import { apiRequest } from "@/lib/api/client";
import type {
  AccountExportBundle,
  AuthPrincipal,
  GazetteerMatch,
  SavedLocation,
  SessionRecord,
  UserMe,
} from "@/types/api";
import type {
  ForgotPasswordFormValues,
  LoginFormValues,
  PreferencesFormValues,
  ProfileSettingsFormValues,
  RegisterFormValues,
  ResetPasswordFormValues,
  SavedLocationFormValues,
} from "@/lib/validation/identity";

export const identityApi = {
  getMePrincipal: () => apiRequest<AuthPrincipal>("/auth/me"),

  register: (values: RegisterFormValues) =>
    apiRequest<AuthPrincipal>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ ...values, locale: "en" }),
    }),

  login: (values: LoginFormValues) =>
    apiRequest<AuthPrincipal>("/auth/login", {
      method: "POST",
      body: JSON.stringify(values),
    }),

  logout: () =>
    apiRequest<{ status: string }>("/auth/logout", {
      method: "POST",
    }),

  forgotPassword: (values: ForgotPasswordFormValues) =>
    apiRequest<{ message: string }>("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify(values),
    }),

  resetPassword: (values: ResetPasswordFormValues) =>
    apiRequest<{ status: string }>("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify(values),
    }),

  verifyEmail: (token: string) =>
    apiRequest<{ status: string }>("/auth/verify-email", {
      method: "POST",
      body: JSON.stringify({ token }),
    }),

  listSessions: () => apiRequest<SessionRecord[]>("/auth/sessions"),

  revokeSession: (sessionId: string) =>
    apiRequest<{ status: string }>(`/auth/sessions/${encodeURIComponent(sessionId)}`, {
      method: "DELETE",
    }),

  revokeOtherSessions: () =>
    apiRequest<{ revoked_count: number }>("/auth/sessions/revoke-others", {
      method: "POST",
    }),

  getUserProfileAndPreferences: () => apiRequest<UserMe>("/users/me"),

  updateProfile: (profile: ProfileSettingsFormValues) =>
    apiRequest<UserMe>("/users/me", {
      method: "PATCH",
      body: JSON.stringify({ profile }),
    }),

  updatePreferences: (preferences: Partial<PreferencesFormValues> & { save_chat_history?: boolean }) =>
    apiRequest<UserMe>("/users/me", {
      method: "PATCH",
      body: JSON.stringify({ preferences }),
    }),

  exportAccountData: () => apiRequest<AccountExportBundle>("/users/me/export"),

  deleteAccount: () =>
    apiRequest<{ status: string }>("/users/me", {
      method: "DELETE",
    }),

  searchCities: (query: string) =>
    apiRequest<GazetteerMatch[]>(`/locations/search?q=${encodeURIComponent(query)}`),

  listSavedLocations: () => apiRequest<SavedLocation[]>("/locations"),

  createSavedLocation: (values: SavedLocationFormValues) =>
    apiRequest<SavedLocation>("/locations", {
      method: "POST",
      body: JSON.stringify({
        label: values.label,
        display_name: values.display_name,
        city: values.city,
        state_region: values.state_region ? values.state_region : null,
        country_code: values.country_code.toUpperCase(),
        postal_code: values.postal_code ? values.postal_code : null,
        location_precision: values.location_precision,
        latitude: values.location_precision === "city" ? null : values.latitude,
        longitude: values.location_precision === "city" ? null : values.longitude,
        timezone: values.timezone,
        is_primary: values.is_primary,
      }),
    }),

  setPrimaryLocation: (locationId: string) =>
    apiRequest<SavedLocation>(`/locations/${encodeURIComponent(locationId)}`, {
      method: "PATCH",
      body: JSON.stringify({ is_primary: true }),
    }),

  deleteSavedLocation: (locationId: string) =>
    apiRequest<{ status: string }>(`/locations/${encodeURIComponent(locationId)}`, {
      method: "DELETE",
    }),
};
