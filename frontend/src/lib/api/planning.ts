import { apiRequest } from "@/lib/api/client";
import type { AQIStandard } from "@/types/api";
import type {
  ActionType,
  DailyRoutine,
  EmissionFactor,
  ImpactCalculationPayload,
  ImpactEstimate,
  ImpactSummary,
  LoggedUserAction,
  RecommendationCard,
  RecommendationFeedbackStatus,
  RoutineActivityEditable,
  RoutineStatus,
} from "@/types/planning";

export const planningApi = {
  listEmissionFactors: (category?: "transport" | "electricity_grid") =>
    apiRequest<EmissionFactor[]>(
      category ? `/impact/factors?category=${encodeURIComponent(category)}` : "/impact/factors",
    ),

  calculateImpact: (payload: ImpactCalculationPayload) =>
    apiRequest<ImpactEstimate>("/impact/calculate", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  logUserAction: (payload: {
    action_type: ActionType;
    title: string;
    quantity: number;
    unit: string;
    calculation?: ImpactCalculationPayload;
  }) =>
    apiRequest<LoggedUserAction>("/impact/actions", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getImpactSummary: () => apiRequest<ImpactSummary>("/impact/summary"),

  getImpactHistory: () => apiRequest<LoggedUserAction[]>("/impact/history"),

  generateRoutine: (payload: {
    city: string;
    standard: AQIStandard;
    commute_distance_km: number;
  }) =>
    apiRequest<DailyRoutine>("/routines/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listRoutines: () => apiRequest<DailyRoutine[]>("/routines"),

  getRoutine: (routineId: string) => apiRequest<DailyRoutine>(`/routines/${routineId}`),

  updateRoutine: (
    routineId: string,
    payload: {
      status?: RoutineStatus;
      activities?: RoutineActivityEditable[];
    },
  ) =>
    apiRequest<DailyRoutine>(`/routines/${routineId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  deleteRoutine: (routineId: string) =>
    apiRequest<{ status: string }>(`/routines/${routineId}`, {
      method: "DELETE",
    }),

  getTodayRecommendations: () => apiRequest<RecommendationCard[]>("/recommendations/today"),

  generateRecommendations: (payload: {
    city: string;
    standard: AQIStandard;
    commute_distance_km?: number;
    use_ai_phrasing?: boolean;
    ai_consent?: boolean;
  }) =>
    apiRequest<RecommendationCard[]>("/recommendations/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  submitRecommendationFeedback: (
    recommendationId: string,
    payload: { status: RecommendationFeedbackStatus; note?: string },
  ) =>
    apiRequest<{ id: string; status: RecommendationFeedbackStatus }>(
      `/recommendations/${recommendationId}/feedback`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),
};
