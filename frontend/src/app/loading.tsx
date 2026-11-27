/**
 * Accessible route-segment loading skeleton for Next.js App Router transitions.
 */

import { WorkspaceSkeleton } from "@/components/ui/workspace-state";

export default function AppLoading() {
  return (
    <main id="main-content" className="mx-auto max-w-5xl px-6 py-10">
      <WorkspaceSkeleton label="Loading AirWise page..." className="h-64" />
    </main>
  );
}
