import Link from "next/link";
import { SettingsSubnav } from "@/components/settings/settings-subnav";

const SETTINGS_CARDS = [
  {
    title: "Profile & Active Sessions",
    href: "/dashboard/settings/profile",
    description:
      "Update your display name, preferred AQI standard (India NAQI vs US EPA), timezone, and revoke active sessions.",
  },
  {
    title: "Saved Locations",
    href: "/dashboard/settings/locations",
    description:
      "Configure Home, Workplace, and School locations with coarse city default and explicit precision controls.",
  },
  {
    title: "Household & Commute Preferences",
    href: "/dashboard/settings/preferences",
    description:
      "Optional household sensitivity, HEPA purifier, cooking/ventilation, and commute mode settings.",
  },
  {
    title: "Privacy, JSON Export & Account Erasure",
    href: "/dashboard/settings/privacy",
    description:
      "Control Copilot chat persistence, download your portable JSON archive, or permanently erase your account.",
  },
] as const;

export default function AccountSettingsOverviewPage() {
  return (
    <main id="main-content" className="mx-auto max-w-5xl px-6 py-10">
      <SettingsSubnav />
      <h1 className="text-2xl font-bold text-text-primary">Account Settings</h1>
      <p className="mt-2 text-sm text-text-secondary">
        Manage profile, saved locations, lifestyle preferences, and GDPR/DPDP privacy controls.
      </p>

      <section className="mt-6 grid gap-5 sm:grid-cols-2">
        {SETTINGS_CARDS.map((card) => (
          <Link
            key={card.href}
            href={card.href}
            className="rounded-card border border-border bg-surface p-5 shadow-sm transition-colors hover:border-brand-primary"
          >
            <h2 className="text-base font-semibold text-text-primary">{card.title}</h2>
            <p className="mt-2 text-sm text-text-secondary">{card.description}</p>
          </Link>
        ))}
      </section>
    </main>
  );
}