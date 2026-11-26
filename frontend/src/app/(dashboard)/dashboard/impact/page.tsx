import { ImpactTrackerWorkspace } from "@/features/impact/impact-tracker-workspace";

export default function RoutePage() {
  return (
    <main id="main-content" className="mx-auto max-w-5xl px-6 py-10">
      <h1 className="text-2xl font-bold text-text-primary">Environmental Impact Tracker</h1>
      <p className="mt-2 text-sm text-text-secondary">Deterministic exposure, transport CO2e, and household energy estimates with transparent assumptions.</p>
      <ImpactTrackerWorkspace />
    </main>
  );
}