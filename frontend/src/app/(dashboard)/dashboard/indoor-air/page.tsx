import { IndoorAirWorkspace } from "@/features/impact/indoor-air-workspace";

export default function RoutePage() {
  return (
    <main id="main-content" className="mx-auto max-w-5xl px-6 py-10">
      <h1 className="text-2xl font-bold text-text-primary">Indoor Air Quality</h1>
      <p className="mt-2 text-sm text-text-secondary">HEPA filtration sizing, cooking exhaust, wet cleaning, and window ventilation timing.</p>
      <IndoorAirWorkspace />
    </main>
  );
}