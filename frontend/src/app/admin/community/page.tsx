import { AdminSubnav } from "@/components/layout/admin-subnav";
import { AdminModerationWorkspace } from "@/features/community/admin-moderation-workspace";

export default function RoutePage() {
  return (
    <main id="main-content" className="mx-auto max-w-5xl px-6 py-10">
      <h1 className="text-2xl font-bold text-text-primary">Admin · Community Moderation</h1>
      <p className="mt-2 text-sm text-text-secondary">Review neighborhood initiatives and abuse reports.</p>
      <AdminSubnav />
      <AdminModerationWorkspace />
    </main>
  );
}