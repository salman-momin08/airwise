import fs from "node:fs";
import path from "node:path";
import React from "react";
import axe from "axe-core";
import { cleanup, render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import LandingPage from "@/app/(public)/page";
import { AQIBadge } from "@/components/air-quality/aqi-badge";
import { ForecastStrip } from "@/components/air-quality/forecast-strip";
import { LocationStandardToolbar } from "@/components/air-quality/location-standard-toolbar";
import { PollutantBreakdownGrid } from "@/components/air-quality/pollutant-breakdown-grid";
import { ProvenanceBanner } from "@/components/air-quality/provenance-banner";
import { GuidanceCard } from "@/components/assistant/guidance-card";
import { ImpactEstimateCard } from "@/components/impact/impact-estimate-card";
import { LoginForm } from "@/features/auth/login-form";
import { RegisterForm } from "@/features/auth/register-form";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/",
}));

afterEach(() => {
  cleanup();
});

async function assertZeroAxeViolations(container: HTMLElement): Promise<void> {
  const results = await axe.run(container, {
    runOnly: {
      type: "tag",
      values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"],
    },
    rules: {
      // JSDOM does not compute CSS custom-property stylesheets; contrast is verified
      // deterministically against globals.css token definitions below.
      "color-contrast": { enabled: false },
    },
  });
  const summary = results.violations.map(
    (v) => `${v.id} (${v.impact}): ${v.help} -> ${v.nodes.map((n) => n.html).join(" | ")}`,
  );
  expect(summary).toEqual([]);
}

function srgbChannelToLinear(channel8Bit: number): number {
  const c = channel8Bit / 255;
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

function relativeLuminance(hex: string): number {
  const clean = hex.replace("#", "").trim();
  const r = Number.parseInt(clean.slice(0, 2), 16);
  const g = Number.parseInt(clean.slice(2, 4), 16);
  const b = Number.parseInt(clean.slice(4, 6), 16);
  return (
    0.2126 * srgbChannelToLinear(r) +
    0.7152 * srgbChannelToLinear(g) +
    0.0722 * srgbChannelToLinear(b)
  );
}

function contrastRatio(hexA: string, hexB: string): number {
  const lumA = relativeLuminance(hexA);
  const lumB = relativeLuminance(hexB);
  const lighter = Math.max(lumA, lumB);
  const darker = Math.min(lumA, lumB);
  return (lighter + 0.05) / (darker + 0.05);
}

function extractThemeVariables(cssBlock: string): Record<string, string> {
  const vars: Record<string, string> = {};
  const regex = /(--[a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;/g;
  let match = regex.exec(cssBlock);
  while (match) {
    const key = match[1];
    const value = match[2];
    if (key && value) {
      vars[key] = value;
    }
    match = regex.exec(cssBlock);
  }
  return vars;
}

describe("WCAG 2.2 Level AA Accessibility & Contrast Suite", () => {
  it("passes axe-core WCAG 2.2 AA rules on public landing page and AQI telemetry widgets", async () => {
    const landing = render(<LandingPage />);
    await assertZeroAxeViolations(landing.container);
    cleanup();

    const widgets = render(
      <main>
        <h1>Air Quality Widgets</h1>
        <LocationStandardToolbar
          selectedCity="Delhi"
          onCityChange={vi.fn()}
          standard="india_naqi"
          onStandardChange={vi.fn()}
        />
        <AQIBadge standard="india_naqi" aqi={356} category="Very Poor" />
        <AQIBadge standard="us_epa" aqi={168} category="Unhealthy" />
        <AQIBadge standard="india_naqi" aqi={null} category={null} />
        <ProvenanceBanner
          provider="openaq"
          sourceType="station"
          measuredAt="2026-11-26T09:00:00Z"
          isStale={true}
          isDevelopmentFixture={false}
        />
        <PollutantBreakdownGrid
          standard="india_naqi"
          dominantPollutant="pm25"
          pollutants={[
            {
              pollutant: "pm25",
              concentration: 188.4,
              unit: "ug/m3",
              averaging_period_hours: 24,
              sub_index: 352,
            },
          ]}
        />
        <ForecastStrip
          isLoading={false}
          isError={false}
          forecast={{
            city: "Delhi",
            standard: "india_naqi",
            provider: "open_meteo",
            source_type: "model",
            generated_at: "2026-11-26T09:00:00Z",
            is_stale: false,
            is_development_fixture: false,
            points: [
              {
                forecast_for: "2026-11-26T14:00:00Z",
                aqi: 145,
                category: "Moderate",
                dominant_pollutant: "pm25",
                pm25_ug_m3: 72,
                confidence_level: "medium",
                safer_outdoor_window: true,
              },
            ],
          }}
        />
      </main>,
    );
    await assertZeroAxeViolations(widgets.container);
  });

  it("passes axe-core WCAG 2.2 AA rules on Copilot GuidanceCard, ImpactEstimateCard, and Auth forms", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });

    const rendered = render(
      <QueryClientProvider client={queryClient}>
        <main>
          <h1>Interactive Guidance and Auth Forms</h1>
          <GuidanceCard
            guidance={{
              situation_summary: "Elevated winter PM2.5 requires indoor filtration.",
              environmental_conditions: {
                standard: "india_naqi",
                status: "available",
                notice: "Verified station observation.",
                reading: {
                  city: "Delhi",
                  standard: "india_naqi",
                  status: "available",
                  aqi: 328,
                  category: "Very Poor",
                  provider: "openaq",
                  source_type: "station",
                  measured_at: "2026-11-26T08:30:00Z",
                  is_stale: false,
                  is_development_fixture: false,
                },
              },
              recommended_action: "Shift vigorous exercise indoors and run a HEPA purifier.",
              why_this_helps: "Reduces inhaled fine particulate concentration.",
              estimated_impact: {
                metric: "transport_co2e",
                baseline_value: 1.92,
                alternative_value: 0.34,
                estimated_difference: 1.58,
                unit: "kg_co2e",
                methodology: "passenger_km_emission_factor",
                assumptions: ["10 km one-way commute"],
                source_references: ["India GHG Program (2023)"],
                confidence: "medium",
                is_estimate: true,
                calculated_at: "2026-11-26T08:30:00Z",
              },
              uncertainty_or_limitations: "Indoor air quality is unmeasured without a sensor.",
              safer_alternative: "Use enclosed metro transit rather than roadside cycling.",
              evidence_references: [
                {
                  document_id: "11111111-1111-4111-8111-111111111111",
                  title: "WHO Global Air Quality Guidelines",
                  publisher: "World Health Organization",
                  source_url: "https://www.who.int/publications/i/item/9789240034228",
                  last_reviewed_date: "2026-10-01T00:00:00Z",
                  freshness_note: null,
                },
              ],
            }}
          />
          <ImpactEstimateCard
            estimate={{
              metric: "indoor_filtration_ach",
              baseline_value: 0.5,
              alternative_value: 4.8,
              estimated_difference: 4.3,
              unit: "clean_air_changes_per_hour",
              methodology: "room_volume_cadr_ach",
              assumptions: ["Room volume 45 m³", "CADR 220 m³/h"],
              source_references: ["US EPA Guide to Air Cleaners in the Home"],
              confidence: "high",
              is_estimate: true,
              calculated_at: "2026-11-26T09:00:00Z",
            }}
          />
          <LoginForm />
          <RegisterForm />
        </main>
      </QueryClientProvider>,
    );
    await assertZeroAxeViolations(rendered.container);
  });

  it("enforces >= 4.5:1 WCAG 2.2 AA contrast ratios across light and dark design tokens", () => {
    const cssPath = path.resolve(__dirname, "../src/app/globals.css");
    const css = fs.readFileSync(cssPath, "utf8");
    const rootBlock = css.match(/:root\s*\{([\s\S]*?)\}/)?.[1] ?? "";
    const darkBlock = css.match(/\.dark\s*\{([\s\S]*?)\}/)?.[1] ?? "";

    const light = extractThemeVariables(rootBlock);
    const dark = extractThemeVariables(darkBlock);

    // Light mode AA checks (>= 4.5:1 normal text)
    expect(contrastRatio(light["--text-primary"]!, light["--background"]!)).toBeGreaterThanOrEqual(4.5);
    expect(contrastRatio(light["--text-primary"]!, light["--surface"]!)).toBeGreaterThanOrEqual(4.5);
    expect(contrastRatio(light["--text-primary"]!, light["--brand-accent"]!)).toBeGreaterThanOrEqual(4.5);
    expect(contrastRatio(light["--text-secondary"]!, light["--background"]!)).toBeGreaterThanOrEqual(4.5);
    expect(contrastRatio(light["--text-secondary"]!, light["--surface"]!)).toBeGreaterThanOrEqual(4.5);
    expect(contrastRatio("#FFFFFF", light["--brand-primary"]!)).toBeGreaterThanOrEqual(4.5);
    expect(contrastRatio(light["--brand-primary"]!, light["--surface"]!)).toBeGreaterThanOrEqual(4.5);

    // Dark mode AA checks (>= 4.5:1 normal text, including dark:text-background on bg-brand-primary)
    expect(contrastRatio(dark["--text-primary"]!, dark["--background"]!)).toBeGreaterThanOrEqual(4.5);
    expect(contrastRatio(dark["--text-primary"]!, dark["--surface"]!)).toBeGreaterThanOrEqual(4.5);
    expect(contrastRatio(dark["--text-primary"]!, dark["--brand-accent"]!)).toBeGreaterThanOrEqual(4.5);
    expect(contrastRatio(dark["--text-secondary"]!, dark["--background"]!)).toBeGreaterThanOrEqual(4.5);
    expect(contrastRatio(dark["--text-secondary"]!, dark["--surface"]!)).toBeGreaterThanOrEqual(4.5);
    expect(contrastRatio(dark["--background"]!, dark["--brand-primary"]!)).toBeGreaterThanOrEqual(4.5);
    expect(contrastRatio(dark["--brand-primary"]!, dark["--surface"]!)).toBeGreaterThanOrEqual(4.5);

    // Reduced-motion and keyboard focus-visible rules exist in globals.css
    expect(css).toContain("prefers-reduced-motion: reduce");
    expect(css).toContain(":focus-visible");
  });
});
