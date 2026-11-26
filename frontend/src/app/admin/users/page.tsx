import { AdminSubnav } from "@/components/layout/admin-subnav";
import { AdminUsersWorkspace } from "@/features/admin/admin-overview-and-users";

export default function RoutePage() {
  return (
    <main id="main-content" className="mx-auto max-w-5xl px-6 py-10">
      <h1 className="text-2xl font-bold text-text-primary">Admin · User Governance</h1>
      <p className="mt-2 text-sm text-text-secondary">Role management and account status administration.</p>
      <AdminSubnav />
      <AdminUsersWorkspace />
    </main>
  );
}