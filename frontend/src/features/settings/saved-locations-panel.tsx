"use client";

/**
 * Saved Locations settings panel enforcing minimum-precision privacy defaults.
 */

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { WorkspaceSkeleton } from "@/components/ui/workspace-state";
import {
  AddSavedLocationFormSection,
  captureVoluntaryBrowserGeolocation,
  SavedLocationsErrorNotice,
  SavedLocationsListSection,
} from "@/features/settings/saved-locations-sections";
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
    return <WorkspaceSkeleton label="Loading saved locations..." className="h-48" />;
  }

  if (locationsQuery.isError) {
    return <SavedLocationsErrorNotice error={locationsQuery.error} />;
  }

  const locations = locationsQuery.data ? locationsQuery.data.data : [];
  const gazetteerMatches = gazetteerQuery.data ? gazetteerQuery.data.data : [];
  const createErrorText =
    createMutation.error instanceof ApiClientError
      ? createMutation.error.message
      : "Unable to save location.";

  return (
    <div className="space-y-8">
      <SavedLocationsListSection
        locations={locations}
        onSetPrimary={(id) => setPrimaryMutation.mutate(id)}
        onRemove={(id) => deleteMutation.mutate(id)}
      />

      <AddSavedLocationFormSection
        form={form}
        precision={precision}
        searchInput={searchInput}
        gazetteerMatches={gazetteerMatches}
        isError={createMutation.isError}
        errorText={createErrorText}
        isPending={createMutation.isPending}
        geoStatus={geoStatus}
        onSearchChange={setSearchInput}
        onSelectMatch={applyGazetteerSelection}
        onRequestGeo={() => captureVoluntaryBrowserGeolocation(form, setGeoStatus)}
        onSubmit={(values) => createMutation.mutate(values)}
      />
    </div>
  );
}
