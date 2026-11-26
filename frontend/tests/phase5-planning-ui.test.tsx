import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ImpactEstimateCard } from "@/components/impact/impact-estimate-card";
import { IndoorAirWorkspace } from "@/features/impact/indoor-air-workspace";
import { RoutinePlannerWorkspace } from "@/features/routines/routine-planner-workspace";
import { airQualityApi } from "@/lib/api/air-quality";
import { planningApi } from "@/lib/api/planning";
import type { DailyRoutine, ImpactEstimate } from "@/types/planning";

vi.mock("@/lib/api/planning", () => ({
  planningApi: {
    listEmissionFactors: vi.fn(),
    calculateImpact: vi.fn(),
    logUserAction: vi.fn(),
    getImpactSummary: vi.fn(),
    getImpactHistory: vi.fn(),
    generateRoutine: vi.fn(),
    listRoutines: vi.fn(),
    getRoutine: vi.fn(),
    updateRoutine: vi.fn(),
    deleteRoutine: vi.fn(),
    getTodayRecommendations: vi.fn(),
    generateRecommendations: vi.fn(),
    submitRecommendationFeedback: vi.fn(),
  },
}));

vi.mock("@/lib/api/air-quality", () => ({
  airQualityApi: {
    getCurrent: vi.fn(),
  },
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function withQueryClient(node: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
}

describe("Phase 5 Impact, Indoor Air & Routine Planner UI", () => {
  it("renders exposure-first safety override alerts alongside deterministic estimates", () => {
    const estimate: ImpactEstimate = {
      metric: "transport_co2e",
      baseline_value: 1.68,
      alternative_value: 0,
      estimated_difference: 1.68,
      unit: "kg_co2e",
      methodology: "passenger_km_emission_factor",
      assumptions: ["Trip distance: 10.00 km"],
      source_references: ["India GHG Program"],
      confidence: "medium",
      is_estimate: true,
      calculated_at: "2026-11-26T12:00:00Z",
      exposure_screening: {
        evaluated: true,
        city: "Delhi",
        standard: "india_naqi",
        aqi: 420,
        category: "Severe",
        is_stale: false,
        is_development_fixture: false,
        recommended_for_current_aqi: false,
        exposure_warning:
          "Exposure-First Safety Override: bicycle reduces tailpipe CO2e, but severe smog makes roadside cycling unsafe.",
        safer_commute_fallback: "Choose enclosed Urban Metro/Rail.",
        indoor_air_measured: false,
      },
    };

    render(<ImpactEstimateCard estimate={estimate} />);
    expect(screen.getByRole("alert").textContent).toContain("Exposure-First Safety Override");
    expect(screen.getByText(/Model Estimate \(is_estimate: true\)/)).toBeTruthy();
    expect(screen.getByText(/Choose enclosed Urban Metro\/Rail/)).toBeTruthy();
  });

  it("displays an honest unmeasured indoor air notice and prohibits ozone/houseplant myths", async () => {
    vi.mocked(airQualityApi.getCurrent).mockResolvedValue({
      meta: { request_id: "req-1", timestamp: "2026-11-26T12:00:00Z" },
      data: {
        city: "Delhi",
        location_precision: "city",
        standard: "india_naqi",
        status: "available",
        aqi: 340,
        category: "Very Poor",
        dominant_pollutant: "pm25",
        pollutants: [],
        measured_at: "2026-11-26T11:45:00Z",
        provider: "fixture",
        source_type: "station",
        is_stale: false,
        is_development_fixture: true,
        precaution_summary: "Keep exterior windows closed.",
        unavailable_reason: null,
      },
    });

    withQueryClient(<IndoorAirWorkspace />);
    expect(
      screen.getByText(/Indoor Air Quality Status: Unmeasured \(No Indoor PM2\.5 Sensor Connected\)/),
    ).toBeTruthy();
    expect(screen.getByText(/No ozone\/ionizer cleaners/)).toBeTruthy();
    expect(screen.getByText(/No houseplant PM2\.5 myths/)).toBeTruthy();
  });

  it("keeps generated routines in unconfirmed draft state until explicitly confirmed", async () => {
    const draftRoutine: DailyRoutine = {
      id: "22222222-2222-4222-8222-222222222222",
      location_id: null,
      city: "Delhi",
      plan_date: "2026-11-26",
      aqi_standard: "india_naqi",
      status: "draft",
      environmental_snapshot_at: "2026-11-26T12:00:00Z",
      environmental_summary: null,
      requires_explicit_confirmation: true,
      created_at: "2026-11-26T12:00:00Z",
      updated_at: "2026-11-26T12:00:00Z",
      activities: [
        {
          id: "33333333-3333-4333-8333-333333333333",
          slot_order: 0,
          time_block: "morning",
          start_time: "07:00",
          duration_minutes: 45,
          title: "Indoor Mobility & Stretching",
          environment_type: "indoor",
          exposure_note: "Avoids morning smog peak.",
          safer_alternative: "Run HEPA purifier.",
          explanation: "Priority 1: Exposure Safety.",
          safety_warning: null,
          impact_estimate: null,
          confidence: "medium",
        },
      ],
    };

    vi.mocked(planningApi.listRoutines).mockResolvedValue({
      meta: { request_id: "req-2", timestamp: "2026-11-26T12:00:00Z" },
      data: [draftRoutine],
    });
    vi.mocked(planningApi.updateRoutine).mockResolvedValue({
      meta: { request_id: "req-3", timestamp: "2026-11-26T12:01:00Z" },
      data: {
        ...draftRoutine,
        status: "confirmed",
        requires_explicit_confirmation: false,
      },
    });

    withQueryClient(<RoutinePlannerWorkspace />);
    expect(await screen.findByText(/Unconfirmed Draft:/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Confirm & Save Schedule" }));
    await waitFor(() => expect(planningApi.updateRoutine).toHaveBeenCalledTimes(1));
    expect(vi.mocked(planningApi.updateRoutine).mock.calls[0]?.[1]).toEqual({
      status: "confirmed",
      activities: undefined,
    });
  });
});
