import { SettingsSubnav } from "@/components/settings/settings-subnav";
import { PreferencesPanel } from "@/features/settings/preferences-panel";

export default function PreferencesSettingsPage() {
  return (
    <main id="main-content" className="mx-auto max-w-5xl px-6 py-10">
      <SettingsSubnav />
      <h1 className="text-2xl font-bold text-text-primary">Lifestyle &amp; Household Preferences</h1>
      <p className="mt-2 mb-6 text-sm text-text-secondary">
        Optional household sensitivity, commute, ventilation, purifier, and budget settings.
      </p>
      <PreferencesPanel />
    </main>
  );
}
