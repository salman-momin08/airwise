import { SettingsSubnav } from "@/components/settings/settings-subnav";
import { SavedLocationsPanel } from "@/features/settings/saved-locations-panel";

export default function SavedLocationsSettingsPage() {
  return (
    <main id="main-content" className="mx-auto max-w-5xl px-6 py-10">
      <SettingsSubnav />
      <h1 className="text-2xl font-bold text-text-primary">Saved Locations</h1>
      <p className="mt-2 mb-6 text-sm text-text-secondary">
        Configure Home, Workplace, and School locations with explicit precision controls and zero
        forced geolocation.
      </p>
      <SavedLocationsPanel />
    </main>
  );
}
