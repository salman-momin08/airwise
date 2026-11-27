import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { AirQualityTrendsChart } from "@/components/air-quality/air-quality-trends-chart";
import { AQIBadge } from "@/components/air-quality/aqi-badge";
import { PollutantBreakdownGrid } from "@/components/air-quality/pollutant-breakdown-grid";
import { ProvenanceBanner } from "@/components/air-quality/provenance-banner";

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === "undefined") {
    globalThis.ResizeObserver = class ResizeObserver {
      observe() {}
      unobserve() {}
      disconnect() {}
    };
  }
});

afterEach(() => {
  cleanup();
});

describe("Air Quality Accessibility & Provenance UI", () => {
  it("renders non-color-only AQI badges with explicit standard and category text", () => {
    render(<AQIBadge standard="india_naqi" aqi={342} category="Very Poor" />);
    const status = screen.getByRole("status");
    expect(status.textContent).toContain("AQI 342");
    expect(status.textContent).toContain("Very Poor");
    expect(status.textContent).toContain("India NAQI");
  });

  it("surfaces staleness and development fixture warnings transparently", () => {
    render(
      <ProvenanceBanner
        provider="openweather"
        sourceType="model"
        measuredAt="2026-11-24T18:00:00Z"
        isStale={true}
        isDevelopmentFixture={true}
      />,
    );
    expect(screen.getByRole("alert").textContent).toContain("Stale Reading Warning");
    expect(screen.getByRole("status").textContent).toContain(
      "Development Synthetic Fixture Active",
    );
    expect(screen.getByText(/Regional Atmospheric Model/i)).toBeTruthy();
  });

  it("renders normalized pollutant sub-indices and dominant badge", () => {
    render(
      <PollutantBreakdownGrid
        standard="us_epa"
        dominantPollutant="pm25"
        pollutants={[
          {
            pollutant: "pm25",
            concentration: 145.2,
            unit: "ug/m3",
            averaging_period_hours: 24,
            sub_index: 220,
          },
        ]}
      />,
    );
    expect(screen.getByText("Dominant")).toBeTruthy();
    expect(screen.getByText(/145.2/)).toBeTruthy();
    expect(screen.getByText("220")).toBeTruthy();
  });

  it("preserves unavailable null history points without fabricating zero AQI values", () => {
    render(
      <AirQualityTrendsChart
        history={{
          city: "Delhi",
          standard: "india_naqi",
          period: "24h",
          provider: "openaq",
          source_type: "station",
          is_stale: false,
          is_development_fixture: false,
          series: [
            {
              timestamp: "2026-11-26T08:00:00Z",
              aqi: null,
              category: null,
              pm25_ug_m3: null,
              pm10_ug_m3: null,
              dominant_pollutant: null,
            },
          ],
        }}
        period="24h"
        onPeriodChange={vi.fn()}
        isLoading={false}
        isError={false}
        onRetry={vi.fn()}
      />,
    );
    expect(screen.queryByText(/AQI 0/i)).toBeNull();
    expect(
      screen.getByText(/AQI sub-index unavailable/i),
    ).toBeTruthy();
  });
});
