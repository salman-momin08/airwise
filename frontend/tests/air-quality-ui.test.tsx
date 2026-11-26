import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { AQIBadge } from "@/components/air-quality/aqi-badge";
import { PollutantBreakdownGrid } from "@/components/air-quality/pollutant-breakdown-grid";
import { ProvenanceBanner } from "@/components/air-quality/provenance-banner";

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
});
