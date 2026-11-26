import { describe, expect, it } from "vitest";
import { describeAQISeverity } from "@/lib/constants/aqi";

describe("describeAQISeverity", () => {
  it("keeps India NAQI and US EPA labels isolated and non-empty", () => {
    const india = describeAQISeverity("india_naqi", "Very Poor");
    const epa = describeAQISeverity("us_epa", "Unhealthy");

    expect(india.standardLabel).toBe("India NAQI");
    expect(india.categoryLabel).toBe("Very Poor");
    expect(india.severitySymbol.length).toBeGreaterThan(0);

    expect(epa.standardLabel).toBe("US EPA AQI");
    expect(epa.categoryLabel).toBe("Unhealthy");
    expect(india.standardLabel).not.toBe(epa.standardLabel);
  });

  it("handles missing AQI readings transparently without fake values", () => {
    const missing = describeAQISeverity("india_naqi", null);
    expect(missing.categoryLabel).toBe("Unavailable");
  });
});
