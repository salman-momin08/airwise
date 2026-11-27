import { AdminSubnav } from "@/components/layout/admin-subnav";
import { AdminAIMonitoringWorkspace } from "@/features/admin/admin-operations-workspaces";

export default function RoutePage() {
  return (
    <main id="main-content" className="mx-auto max-w-5xl px-6 py-10">
      <h1 className="text-2xl font-bold text-text-primary">Admin · AI Quality & Cost Monitoring</h1>
      <p className="mt-2 text-sm text-text-secondary">Inspect latency, token usage, fallback rates, and safety guardrail metrics.</p>
      <AdminSubnav />
      <AdminAIMonitoringWorkspace />
    </main>
  );
}
