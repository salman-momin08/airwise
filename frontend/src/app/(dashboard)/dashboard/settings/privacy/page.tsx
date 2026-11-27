import { SettingsSubnav } from "@/components/settings/settings-subnav";
import { PrivacyAndDataPanel } from "@/features/settings/privacy-and-data-panel";

export default function PrivacySettingsPage() {
  return (
    <main id="main-content" className="mx-auto max-w-5xl px-6 py-10">
      <SettingsSubnav />
      <h1 className="text-2xl font-bold text-text-primary">Privacy, Export &amp; Account Deletion</h1>
      <p className="mt-2 mb-6 text-sm text-text-secondary">
        Manage chat retention, download your portable JSON data export, or permanently delete your
        account.
      </p>
      <PrivacyAndDataPanel />
    </main>
  );
}
