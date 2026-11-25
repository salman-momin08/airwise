"use client";

import type { AQIStandard, SavedLocation } from "@/types/api";

const SUPPORTED_CITIES = [
  "Delhi",
  "Gurugram",
  "Noida",
  "Bengaluru",
  "Mumbai",
  "Chennai",
  "Kolkata",
  "Hyderabad",
  "Pune",
  "Lucknow",
] as const;

interface LocationStandardToolbarProps {
  selectedCity: string;
  onCityChange: (city: string) => void;
  standard: AQIStandard;
  onStandardChange: (standard: AQIStandard) => void;
  savedLocations?: SavedLocation[];
}

export function LocationStandardToolbar({
  selectedCity,
  onCityChange,
  standard,
  onStandardChange,
  savedLocations = [],
}: LocationStandardToolbarProps) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4 rounded-card border border-border bg-surface p-4 shadow-sm">
      <div className="flex flex-wrap items-end gap-4">
        <div>
          <label
            htmlFor="aqi-city-selector"
            className="block text-xs font-semibold uppercase tracking-wide text-text-secondary"
          >
            City (Consent-first — no forced GPS)
          </label>
          <select
            id="aqi-city-selector"
            value={selectedCity}
            onChange={(e) => onCityChange(e.target.value)}
            className="mt-1 rounded-lg border border-border bg-background px-3 py-2 text-sm font-medium text-text-primary focus:outline-none focus:ring-2 focus:ring-brand-primary"
          >
            {SUPPORTED_CITIES.map((city) => (
              <option key={city} value={city}>
                {city}
              </option>
            ))}
          </select>
        </div>

        {savedLocations.length > 0 ? (
          <div>
            <span className="block text-xs font-semibold uppercase tracking-wide text-text-secondary">
              Saved Places
            </span>
            <div className="mt-1 flex flex-wrap gap-2">
              {savedLocations.map((loc) => (
                <button
                  key={loc.id}
                  type="button"
                  onClick={() => onCityChange(loc.city)}
                  className={`rounded-lg border px-3 py-1.5 text-xs font-medium ${
                    selectedCity.toLowerCase() === loc.city.toLowerCase()
                      ? "border-brand-primary bg-brand-accent/50 text-text-primary"
                      : "border-border bg-background text-text-secondary hover:text-text-primary"
                  }`}
                >
                  {loc.display_name} ({loc.city})
                </button>
              ))}
            </div>
          </div>
        ) : null}
      </div>

      <div>
        <span className="block text-xs font-semibold uppercase tracking-wide text-text-secondary">
          Isolated AQI Standard
        </span>
        <div role="group" aria-label="AQI reporting standard" className="mt-1 flex gap-2">
          <button
            type="button"
            aria-pressed={standard === "india_naqi"}
            onClick={() => onStandardChange("india_naqi")}
            className={`rounded-lg px-3 py-2 text-xs font-semibold transition-colors ${
              standard === "india_naqi"
                ? "bg-brand-primary text-white"
                : "border border-border bg-background text-text-primary hover:bg-brand-accent/30"
            }`}
          >
            India NAQI (CPCB)
          </button>
          <button
            type="button"
            aria-pressed={standard === "us_epa"}
            onClick={() => onStandardChange("us_epa")}
            className={`rounded-lg px-3 py-2 text-xs font-semibold transition-colors ${
              standard === "us_epa"
                ? "bg-brand-primary text-white"
                : "border border-border bg-background text-text-primary hover:bg-brand-accent/30"
            }`}
          >
            US EPA AQI
          </button>
        </div>
      </div>
    </div>
  );
}
