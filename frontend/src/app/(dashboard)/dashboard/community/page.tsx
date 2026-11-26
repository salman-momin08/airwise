import { CommunityHubWorkspace } from "@/features/community/community-hub-workspace";

export default function RoutePage() {
  return (
    <main id="main-content" className="mx-auto max-w-5xl px-6 py-10">
      <h1 className="text-2xl font-bold text-text-primary">Neighborhood Clean-Air Community</h1>
      <p className="mt-2 text-sm text-text-secondary">Participate in local challenges with privacy-preserving aggregate impact tracking.</p>
      <CommunityHubWorkspace />
    </main>
  );
}