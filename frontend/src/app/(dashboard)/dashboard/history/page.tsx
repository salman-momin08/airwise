import { ActivityHistoryWorkspace } from "@/features/history/activity-history-workspace";

export default function RoutePage() {
  return (
    <main id="main-content" className="mx-auto max-w-5xl px-6 py-10">
      <h1 className="text-2xl font-bold text-text-primary">Activity & Exposure History</h1>
      <p className="mt-2 text-sm text-text-secondary">Historical routines, completed sustainability actions, and alert logs.</p>
      <ActivityHistoryWorkspace />
    </main>
  );
}
