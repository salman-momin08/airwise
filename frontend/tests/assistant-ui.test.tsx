import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { GuidanceCard, trustedCitationUrl } from "@/components/assistant/guidance-card";
import type { AssistantGuidance } from "@/types/assistant";

afterEach(cleanup);

function guidance(): AssistantGuidance {
  return {
    situation_summary: "General protection guidance.",
    environmental_conditions: {
      standard: "india_naqi", status: "unavailable", reading: null,
      notice: "Verified live air quality is unavailable.",
    },
    recommended_action: "<script>alert('unsafe')</script>",
    why_this_helps: "Source control reduces exposure.",
    estimated_impact: null,
    uncertainty_or_limitations: "Indoor air quality is unmeasured.",
    safer_alternative: "Choose an indoor activity.",
    evidence_references: [{
      document_id: "11111111-1111-4111-8111-111111111111",
      title: "Air cleaner guidance", publisher: "US EPA",
      source_url: "javascript:alert(1)", last_reviewed_date: "2026-11-26T00:00:00Z",
      freshness_note: "This guidance is past its review horizon.",
    }],
  };
}

describe("Grounded assistant guidance", () => {
  it("renders untrusted prose as text and rejects unsafe citation links", () => {
    const { container } = render(<GuidanceCard guidance={guidance()} />);
    expect(container.querySelector("script")).toBeNull();
    expect(screen.getByText("<script>alert('unsafe')</script>")).toBeTruthy();
    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.getByText(/source link unavailable/)).toBeTruthy();
    expect(screen.getByText(/past its review horizon/)).toBeTruthy();
    expect(screen.getByRole("status").textContent).toContain("India NAQI");
    expect(screen.getByText(/Verified live air quality is unavailable/)).toBeTruthy();
  });

  it("makes provenance, staleness and synthetic data visible alongside a standard-specific badge", () => {
    const value = guidance();
    value.environmental_conditions.reading = {
      city: "Delhi", standard: "india_naqi", status: "available", aqi: 450, category: "Severe",
      provider: "fixture", source_type: "model", measured_at: "2026-11-25T00:00:00Z",
      is_stale: true, is_development_fixture: true,
    };
    render(<GuidanceCard guidance={value} />);
    expect(screen.getByText(/AQI 450/)).toBeTruthy();
    expect(screen.getByRole("alert").textContent).toContain("Stale Reading Warning");
    expect(screen.getByText(/Development Synthetic Fixture Active/)).toBeTruthy();
  });

  it("allows only exact official HTTPS citation hosts", () => {
    expect(trustedCitationUrl("https://www.epa.gov/guide")).toBe("https://www.epa.gov/guide");
    for (const url of [
      "https://www.epa.gov.attacker.example/guide", "https://attacker@www.epa.gov/guide",
      "http://www.epa.gov/guide", "data:text/html,test",
    ]) expect(trustedCitationUrl(url)).toBeNull();
  });
});
