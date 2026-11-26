import { AdminSubnav } from "@/components/layout/admin-subnav";
import { AdminOverviewWorkspace } from "@/features/admin/admin-overview-and-users";

export default function AdminOverviewPage() {
  return (
    <main id="main-content" className="mx-auto max-w-5xl px-6 py-10">
      <h1 className="text-2xl font-bold text-text-primary">AirWise Administration</h1>
      <p className="mt-2 text-sm text-text-secondary">
        All administrative actions enforce server-side Administrator RBAC and append-only audit logging
        via <code>/api/v1/admin/*</code>.
      </p>
      <AdminSubnav />
      <AdminOverviewWorkspace />
    </main>
  );
}
