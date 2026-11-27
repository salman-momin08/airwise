import { SettingsSubnav } from "@/components/settings/settings-subnav";
import { ProfileAndSessionsPanel } from "@/features/settings/profile-and-sessions-panel";

export default function ProfileSettingsPage() {
  return (
    <main id="main-content" className="mx-auto max-w-5xl px-6 py-10">
      <SettingsSubnav />
      <h1 className="text-2xl font-bold text-text-primary">Profile &amp; Active Sessions</h1>
      <p className="mt-2 mb-6 text-sm text-text-secondary">
        Manage display name, preferred AQI standard, locale, and active browser sessions.
      </p>
      <ProfileAndSessionsPanel />
    </main>
  );
}
