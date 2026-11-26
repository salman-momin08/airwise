import { RoutinePlannerWorkspace } from "@/features/routines/routine-planner-workspace";

export default function RoutePage() {
  return (
    <main id="main-content" className="mx-auto max-w-5xl px-6 py-10">
      <h1 className="text-2xl font-bold text-text-primary">Personalized Daily Routine Planner</h1>
      <p className="mt-2 text-sm text-text-secondary">Plan Morning through Night activities prioritizing exposure reduction and household schedules.</p>
      <RoutinePlannerWorkspace />
    </main>
  );
}