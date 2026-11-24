"use client";

import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiClientError } from "@/lib/api/client";
import { identityApi } from "@/lib/api/identity";
import {
  savedLocationCreateSchema,
  type SavedLocationFormValues,
} from "@/lib/validation/identity";
import { useLocationStore } from "@/stores/location-store";
import type { GazetteerMatch } from "@/types/api";

export function SavedLocationsPanel() {
  const queryClient = useQueryClient();
  const setSelectedCity = useLocationStore((state) => state.setSelectedCity);
  const [searchInput, setSearchInput] = useState("");
  const [geoStatus, setGeoStatus] = useState<string | null>(null);

  const locationsQuery = useQuery({
    queryKey: ["locations", "saved"],
    queryFn: () => identityApi.listSavedLocations(),
  });

  const gazetteerQuery = useQuery({
    queryKey: ["locations", "search", searchInput.trim()],
    queryFn: () => identityApi.searchCities(searchInput.trim()),
    enabled: searchInput.trim().length >= 2,
  });

  const form = useForm<SavedLocationFormValues>({
    resolver: zodResolver(savedLocationCreateSchema),
    defaultValues: {
      label: "home",
      display_name: "Home",
      city: "Delhi",
      state_region: "NCT of Delhi",
      country_code: "IN",
      postal_code: "",
      location_precision: "city",
      latitude: null,
      longitude: null,
      timezone: "Asia/Kolkata",
      is_primary: true,
    },
  });

  const precision = form.watch("location_precision");

  const applyGazetteerSelection = (match: GazetteerMatch) => {
    form.setValue("city", match.city, { shouldValidate: true });
    form.setValue("state_region", match.state_region);
    form.setValue("country_code", match.country_code);
    form.setValue("timezone", match.timezone);
    setSearchInput("");
  };

  const requestVoluntaryBrowserGeolocation = () => {
    // Consent-first invariant: triggered ONLY from explicit user button click
    if (typeof navigator === "undefined" || !("geolocation" in navigator)) {
      setGeoStatus("Browser geolocation is unavailable on this device. City selection works with full parity.");
      return;
    }
    setGeoStatus("Requesting one-time browser coordinates…");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const roundedLat = Number(pos.coords.latitude.toFixed(4));
        const roundedLon = Number(pos.coords.longitude.toFixed(4));
        form.setValue("latitude", roundedLat, { shouldValidate: true });
        form.setValue("longitude", roundedLon, { shouldValidate: true });
        form.setValue("location_precision", "exact", { shouldValidate: true });
        setGeoStatus(
          `Captured consented coordinates (${roundedLat}, ${roundedLon}). Exact coordinates are never shared with external LLMs.`,
        );
      },
      () => {
        setGeoStatus(
          "Geolocation permission was declined or timed out. Keep 'City only' precision for full feature parity.",
        );
      },
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 60_000 },
    );
  };

  const createMutation = useMutation({
    mutationFn: (values: SavedLocationFormValues) => identityApi.createSavedLocation(values),
    onSuccess: async (res) => {
      if (res.data.is_primary) {
        setSelectedCity(res.data.city);
      }
      await queryClient.invalidateQueries({ queryKey: ["locations", "saved"] });
    },
  });

  const setPrimaryMutation = useMutation({
    mutationFn: (id: string) => identityApi.setPrimaryLocation(id),
    onSuccess: async (res) => {
      setSelectedCity(res.data.city);
      await queryClient.invalidateQueries({ queryKey: ["locations", "saved"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => identityApi.deleteSavedLocation(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["locations", "saved"] });
    },
  });

  if (locationsQuery.isLoading) {
    return (
      <div
        aria-busy="true"
        className="h-48 animate-pulse rounded-card border border-border bg-surface p-6"
      />
    );
  }

  if (locationsQuery.isError) {
    const unauth =
      locationsQuery.error instanceof ApiClientError && locationsQuery.error.status === 401;
    return (
      <div role="alert" className="rounded-card border border-border bg-surface p-6 text-sm">
        {unauth ? (
          <p>
            Please{" "}
            <Link href="/login" className="font-semibold text-brand-primary underline">
              sign in
            </Link>{" "}
            to save Home, Workplace, and School locations, or use{" "}
            <Link href="/air-quality" className="font-semibold text-brand-primary underline">
              public city AQI search
            </Link>{" "}
            without an account.
          </p>
        ) : (
          <p>Unable to load saved locations right now.</p>
        )}
      </div>
    );
  }

  const locations = locationsQuery.data?.data ?? [];

  return (
    <div className="space-y-8">
      <section className="rounded-card border border-border bg-surface p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-text-primary">Your Saved Locations</h2>
        <p className="mt-1 text-xs text-text-secondary">
          Coarse city-level selection is the default. Exact coordinates are optional and never sent
          to external AI models.
        </p>

        {locations.length === 0 ? (
          <p className="mt-4 rounded-lg border border-dashed border-border p-4 text-sm text-text-secondary">
            No saved locations yet. Add your Home, Workplace, or School city below.
          </p>
        ) : (
          <ul className="mt-4 grid gap-4 sm:grid-cols-2">
            {locations.map((loc) => (
              <li
                key={loc.id}
                className="flex flex-col justify-between rounded-card border border-border bg-background p-4"
              >
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-semibold text-text-primary">
                      {loc.display_name}{" "}
                      <span className="text-xs font-normal uppercase text-text-secondary">
                        ({loc.label})
                      </span>
                    </span>
                    {loc.is_primary ? (
                      <span className="rounded bg-brand-accent px-2 py-0.5 text-xs font-semibold text-brand-primary">
                        Primary
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-1 text-xs text-text-secondary">
                    {loc.city}
                    {loc.state_region ? `, ${loc.state_region}` : ""} ({loc.country_code}) ·
                    Precision: <strong className="text-text-primary">{loc.location_precision}</strong>
                  </p>
                </div>

                <div className="mt-4 flex items-center gap-3 text-xs">
                  {!loc.is_primary ? (
                    <button
                      type="button"
                      onClick={() => setPrimaryMutation.mutate(loc.id)}
                      className="font-medium text-brand-primary underline"
                    >
                      Set as primary
                    </button>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => deleteMutation.mutate(loc.id)}
                    className="font-medium text-red-700 underline dark:text-red-300"
                  >
                    Remove
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded-card border border-border bg-surface p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-text-primary">Add a Location</h2>

        <div className="mt-4">
          <label
            htmlFor="gazetteer-search"
            className="block text-sm font-medium text-text-primary"
          >
            Quick city or PIN prefix lookup (no geolocation required)
          </label>
          <input
            id="gazetteer-search"
            type="search"
            placeholder="Search Delhi, Bengaluru, Mumbai, 110, 560…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary"
          />
          {(gazetteerQuery.data?.data ?? []).length > 0 ? (
            <ul className="mt-2 flex flex-wrap gap-2">
              {(gazetteerQuery.data?.data ?? []).map((item) => (
                <li key={`${item.city}-${item.postal_prefix}`}>
                  <button
                    type="button"
                    onClick={() => applyGazetteerSelection(item)}
                    className="rounded-lg border border-brand-primary/40 bg-brand-accent/40 px-3 py-1 text-xs font-medium text-text-primary"
                  >
                    {item.city}, {item.state_region} (PIN {item.postal_prefix}xx)
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </div>

        {createMutation.isError ? (
          <div
            role="alert"
            className="mt-4 rounded-lg border border-red-400/60 bg-red-500/10 p-3 text-sm text-red-700 dark:text-red-300"
          >
            {createMutation.error instanceof ApiClientError
              ? createMutation.error.message
              : "Unable to save location."}
          </div>
        ) : null}

        <form
          onSubmit={form.handleSubmit((values) => createMutation.mutate(values))}
          noValidate
          className="mt-4 grid gap-4 sm:grid-cols-2"
        >
          <div>
            <label htmlFor="loc-label" className="block text-sm font-medium text-text-primary">
              Category
            </label>
            <select
              id="loc-label"
              {...form.register("label")}
              className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary"
            >
              <option value="home">Home</option>
              <option value="workplace">Workplace</option>
              <option value="school">School / Campus</option>
              <option value="other">Other</option>
            </select>
          </div>

          <div>
            <label htmlFor="loc-display" className="block text-sm font-medium text-text-primary">
              Display name
            </label>
            <input
              id="loc-display"
              type="text"
              {...form.register("display_name")}
              className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary"
            />
            {form.formState.errors.display_name ? (
              <p className="mt-1 text-xs text-red-600">
                {form.formState.errors.display_name.message}
              </p>
            ) : null}
          </div>

          <div>
            <label htmlFor="loc-city" className="block text-sm font-medium text-text-primary">
              City
            </label>
            <input
              id="loc-city"
              type="text"
              {...form.register("city")}
              className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary"
            />
          </div>

          <div>
            <label htmlFor="loc-precision" className="block text-sm font-medium text-text-primary">
              Stored precision level
            </label>
            <select
              id="loc-precision"
              {...form.register("location_precision")}
              className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary"
            >
              <option value="city">City only (Recommended privacy default)</option>
              <option value="postal_code">Postal / PIN code area</option>
              <option value="neighborhood">Neighborhood</option>
              <option value="exact">Exact pin / Voluntary GPS</option>
            </select>
            {form.formState.errors.location_precision ? (
              <p className="mt-1 text-xs text-red-600">
                {form.formState.errors.location_precision.message}
              </p>
            ) : null}
          </div>

          {precision !== "city" ? (
            <>
              <div>
                <label
                  htmlFor="loc-postal"
                  className="block text-sm font-medium text-text-primary"
                >
                  Postal / PIN code (optional)
                </label>
                <input
                  id="loc-postal"
                  type="text"
                  {...form.register("postal_code")}
                  className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary"
                />
              </div>

              <div className="flex flex-col justify-end">
                <button
                  type="button"
                  onClick={requestVoluntaryBrowserGeolocation}
                  className="rounded-lg border border-brand-primary px-3 py-2 text-xs font-semibold text-brand-primary hover:bg-brand-accent/30"
                >
                  Use my current browser coordinates (voluntary one-time check)
                </button>
              </div>
            </>
          ) : null}

          {geoStatus ? (
            <p className="text-xs text-text-secondary sm:col-span-2">{geoStatus}</p>
          ) : null}

          <div className="sm:col-span-2">
            <label className="flex items-center gap-2 text-sm text-text-primary">
              <input
                type="checkbox"
                {...form.register("is_primary")}
                className="h-4 w-4 accent-brand-primary"
              />
              Make this my primary dashboard location
            </label>
          </div>

          <div className="sm:col-span-2">
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="rounded-lg bg-brand-primary px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
            >
              {createMutation.isPending ? "Saving location…" : "Save location"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
