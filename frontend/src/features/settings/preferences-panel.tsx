"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiClientError } from "@/lib/api/client";
import { identityApi } from "@/lib/api/identity";
import type { AgeCategory, BudgetTier, CommuteMode } from "@/types/api";

const COMMUTE_OPTIONS: { value: CommuteMode; label: string }[] = [
  { value: "metro_rail", label: "Metro / Urban Rail" },
  { value: "bus", label: "Public Bus" },
  { value: "carpool_3", label: "Carpool (3+ occupants)" },
  { value: "two_wheeler_ev", label: "Electric Two-Wheeler" },
  { value: "two_wheeler_petrol", label: "Petrol Two-Wheeler" },
  { value: "car_ev", label: "Electric Car" },
  { value: "car_solo_petrol", label: "Solo Petrol Car" },
  { value: "bicycle", label: "Bicycle" },
  { value: "walk", label: "Walking" },
  { value: "work_from_home", label: "Work from Home" },
];

export function PreferencesPanel() {
  const queryClient = useQueryClient();
  const [ageCategory, setAgeCategory] = useState<AgeCategory | "">("");
  const [householdSize, setHouseholdSize] = useState<string>("");
  const [hasVulnerable, setHasVulnerable] = useState<boolean>(false);
  const [commuteModes, setCommuteModes] = useState<CommuteMode[]>([]);
  const [cookingType, setCookingType] = useState<string>("");
  const [ventilationType, setVentilationType] = useState<string>("");
  const [hasHepaPurifier, setHasHepaPurifier] = useState<boolean>(false);
  const [budgetTier, setBudgetTier] = useState<BudgetTier | "">("");
  const [savedBanner, setSavedBanner] = useState<string | null>(null);

  const meQuery = useQuery({
    queryKey: ["users", "me"],
    queryFn: () => identityApi.getUserProfileAndPreferences(),
  });

  useEffect(() => {
    const prefs = meQuery.data?.data.preferences;
    if (!prefs) return;
    setAgeCategory(prefs.age_category ?? "");
    setHouseholdSize(prefs.household_size !== null ? String(prefs.household_size) : "");
    setHasVulnerable(Boolean(prefs.has_vulnerable_members));
    setCommuteModes(prefs.commute_modes);
    setCookingType(prefs.cooking_type ?? "");
    setVentilationType(prefs.ventilation_type ?? "");
    setHasHepaPurifier(prefs.has_hepa_purifier);
    setBudgetTier(prefs.budget_tier ?? "");
  }, [meQuery.data]);

  const saveMutation = useMutation({
    mutationFn: () => {
      const parsedSize = householdSize.trim() ? Number.parseInt(householdSize, 10) : null;
      return identityApi.updatePreferences({
        age_category: ageCategory === "" ? null : ageCategory,
        household_size:
          parsedSize !== null && !Number.isNaN(parsedSize)
            ? Math.min(20, Math.max(1, parsedSize))
            : null,
        has_vulnerable_members: hasVulnerable,
        commute_modes: commuteModes,
        cooking_type: cookingType.trim() || null,
        ventilation_type: ventilationType.trim() || null,
        has_hepa_purifier: hasHepaPurifier,
        budget_tier: budgetTier === "" ? null : budgetTier,
      });
    },
    onSuccess: async () => {
      setSavedBanner(
        "Household & commute preferences updated. Exposure-safety guidance will reflect these opt-in settings.",
      );
      await queryClient.invalidateQueries({ queryKey: ["users", "me"] });
    },
  });

  const toggleCommuteMode = (mode: CommuteMode) => {
    setCommuteModes((prev) =>
      prev.includes(mode) ? prev.filter((item) => item !== mode) : [...prev, mode],
    );
  };

  if (meQuery.isLoading) {
    return (
      <div
        aria-busy="true"
        className="h-56 animate-pulse rounded-card border border-border bg-surface p-6"
      />
    );
  }

  if (meQuery.isError) {
    const unauth = meQuery.error instanceof ApiClientError && meQuery.error.status === 401;
    return (
      <div role="alert" className="rounded-card border border-border bg-surface p-6 text-sm">
        {unauth ? (
          <p>
            Please{" "}
            <Link href="/login" className="font-semibold text-brand-primary underline">
              sign in
            </Link>{" "}
            to configure optional household and commute preferences.
          </p>
        ) : (
          <p>Unable to load household preferences right now.</p>
        )}
      </div>
    );
  }

  return (
    <section className="rounded-card border border-border bg-surface p-6 shadow-sm">
      <p className="mb-4 text-xs text-text-secondary">
        All fields are optional. AirWise AI never asks for clinical medical diagnoses and never
        transmits account identifiers to external AI providers.
      </p>

      {savedBanner ? (
        <div
          role="status"
          className="mb-4 rounded-lg border border-brand-secondary/40 bg-brand-accent/40 p-3 text-sm text-text-primary"
        >
          {savedBanner}
        </div>
      ) : null}

      <form
        onSubmit={(event) => {
          event.preventDefault();
          setSavedBanner(null);
          saveMutation.mutate();
        }}
        className="space-y-6"
      >
        <div className="grid gap-4 sm:grid-cols-3">
          <div>
            <label htmlFor="pref-age" className="block text-sm font-medium text-text-primary">
              Primary user age group
            </label>
            <select
              id="pref-age"
              value={ageCategory}
              onChange={(e) => setAgeCategory(e.target.value as AgeCategory | "")}
              className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary"
            >
              <option value="">Prefer not to specify</option>
              <option value="youth">Youth / Student</option>
              <option value="adult">Adult</option>
              <option value="older_adult">Older Adult (60+)</option>
              <option value="prefer_not_to_say">Prefer not to say</option>
            </select>
          </div>

          <div>
            <label
              htmlFor="pref-household"
              className="block text-sm font-medium text-text-primary"
            >
              Household size
            </label>
            <input
              id="pref-household"
              type="number"
              min={1}
              max={20}
              value={householdSize}
              onChange={(e) => setHouseholdSize(e.target.value)}
              className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary"
            />
          </div>

          <div>
            <label htmlFor="pref-budget" className="block text-sm font-medium text-text-primary">
              Filtration / action budget tier
            </label>
            <select
              id="pref-budget"
              value={budgetTier}
              onChange={(e) => setBudgetTier(e.target.value as BudgetTier | "")}
              className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary"
            >
              <option value="">Not specified</option>
              <option value="low">Low-cost / DIY focus</option>
              <option value="moderate">Moderate</option>
              <option value="flexible">Flexible</option>
            </select>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <label className="flex items-start gap-3 rounded-lg border border-border bg-background p-3 text-sm">
            <input
              type="checkbox"
              checked={hasVulnerable}
              onChange={(e) => setHasVulnerable(e.target.checked)}
              className="mt-1 h-4 w-4 accent-brand-primary"
            />
            <span>
              <span className="block font-medium text-text-primary">
                Household includes young children, older adults, or pollution-sensitive members
              </span>
              <span className="text-xs text-text-secondary">
                Applies more conservative outdoor-activity thresholds during elevated PM2.5.
              </span>
            </span>
          </label>

          <label className="flex items-start gap-3 rounded-lg border border-border bg-background p-3 text-sm">
            <input
              type="checkbox"
              checked={hasHepaPurifier}
              onChange={(e) => setHasHepaPurifier(e.target.checked)}
              className="mt-1 h-4 w-4 accent-brand-primary"
            />
            <span>
              <span className="block font-medium text-text-primary">
                Household has a true HEPA indoor air purifier
              </span>
              <span className="text-xs text-text-secondary">
                Tailors indoor filtration and clean-room guidance (ozone generators are never
                recommended).
              </span>
            </span>
          </label>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="pref-cooking" className="block text-sm font-medium text-text-primary">
              Primary cooking setup
            </label>
            <select
              id="pref-cooking"
              value={cookingType}
              onChange={(e) => setCookingType(e.target.value)}
              className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary"
            >
              <option value="">Not specified</option>
              <option value="induction_electric">Induction / Electric</option>
              <option value="lpg_piped_gas_with_chimney">LPG / Piped Gas with Exhaust Hood</option>
              <option value="lpg_piped_gas_no_chimney">LPG / Piped Gas without Exhaust Hood</option>
            </select>
          </div>

          <div>
            <label
              htmlFor="pref-ventilation"
              className="block text-sm font-medium text-text-primary"
            >
              Home ventilation type
            </label>
            <select
              id="pref-ventilation"
              value={ventilationType}
              onChange={(e) => setVentilationType(e.target.value)}
              className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary"
            >
              <option value="">Not specified</option>
              <option value="natural_windows">Natural windows / cross-ventilation</option>
              <option value="split_ac_recirculate">Split AC (recirculation)</option>
              <option value="mechanical_fresh_air_filtered">Filtered mechanical fresh air</option>
            </select>
          </div>
        </div>

        <fieldset>
          <legend className="text-sm font-medium text-text-primary">
            Available commute modes (exposure safety always overrides CO2e savings on smog days)
          </legend>
          <div className="mt-2 grid gap-2 sm:grid-cols-2 md:grid-cols-3">
            {COMMUTE_OPTIONS.map((opt) => (
              <label
                key={opt.value}
                className="flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-xs font-medium text-text-primary"
              >
                <input
                  type="checkbox"
                  checked={commuteModes.includes(opt.value)}
                  onChange={() => toggleCommuteMode(opt.value)}
                  className="h-4 w-4 accent-brand-primary"
                />
                {opt.label}
              </label>
            ))}
          </div>
        </fieldset>

        <button
          type="submit"
          disabled={saveMutation.isPending}
          className="rounded-lg bg-brand-primary px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
        >
          {saveMutation.isPending ? "Saving preferences…" : "Save preferences"}
        </button>
      </form>
    </section>
  );
}
