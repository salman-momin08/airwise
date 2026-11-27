/**
 * Accessible loading state for administrative `/admin/*` governance routes.
 */

import { WorkspaceSkeleton } from "@/components/ui/workspace-state";

export default function AdminLoading() {
  return (
    <main id="main-content" className="mx-auto max-w-5xl px-6 py-10">
      <WorkspaceSkeleton label="Loading administration workspace..." className="h-64" />
    </main>
  );
}
