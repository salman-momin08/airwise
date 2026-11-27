/**
 * Accessible loading state for authenticated `/dashboard/*` routes.
 */

import { WorkspaceSkeleton } from "@/components/ui/workspace-state";

export default function DashboardLoading() {
  return (
    <main id="main-content" className="mx-auto max-w-6xl px-6 py-10">
      <WorkspaceSkeleton label="Loading dashboard workspace..." className="h-64" />
    </main>
  );
}
