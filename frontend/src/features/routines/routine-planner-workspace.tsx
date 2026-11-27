"use client";

/**
 * Interactive Daily Routine Planner workspace coordinating draft generation, slot edits, and confirmation.
 */

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  WorkspaceAuthOrErrorNotice,
  WorkspaceSkeleton,
} from "@/components/ui/workspace-state";
import {
  ActiveRoutineTimelineSection,
  GenerateRoutineFormCard,
  SavedRoutineSelectorBar,
} from "@/features/routines/routine-planner-sections";
import { planningApi } from "@/lib/api/planning";
import {
  generateRoutineFormSchema,
  type GenerateRoutineFormValues,
} from "@/lib/validation/planning";
import { useLocationStore } from "@/stores/location-store";
import type { DailyRoutine, RoutineActivityEditable } from "@/types/planning";

export function RoutinePlannerWorkspace() {
  const queryClient = useQueryClient();
  const storeCity = useLocationStore((s) => s.selectedCity);
  const storeStandard = useLocationStore((s) => s.aqiStandard);

  const [selectedRoutineId, setSelectedRoutineId] = useState<string | null>(null);
  const [editedSlots, setEditedSlots] = useState<RoutineActivityEditable[]>([]);
  const [hasUnsavedEdits, setHasUnsavedEdits] = useState(false);
  const [feedbackBanner, setFeedbackBanner] = useState<string | null>(null);

  const routinesQuery = useQuery({
    queryKey: ["routines", "list"],
    queryFn: () => planningApi.listRoutines(),
    retry: false,
  });

  const form = useForm<GenerateRoutineFormValues>({
    resolver: zodResolver(generateRoutineFormSchema),
    defaultValues: {
      city: storeCity,
      standard: storeStandard,
      commute_distance_km: 10,
    },
  });

  const routines = routinesQuery.data?.data ?? [];
  const activeRoutine: DailyRoutine | undefined =
    routines.find((r) => r.id === selectedRoutineId) ?? routines[0];

  useEffect(() => {
    if (!activeRoutine) {
      setEditedSlots([]);
      setHasUnsavedEdits(false);
      return;
    }
    setSelectedRoutineId(activeRoutine.id);
    setEditedSlots(
      activeRoutine.activities.map((a) => ({
        time_block: a.time_block,
        start_time: a.start_time,
        duration_minutes: a.duration_minutes,
        title: a.title,
        environment_type: a.environment_type,
        safer_alternative: a.safer_alternative,
      })),
    );
    setHasUnsavedEdits(false);
  }, [activeRoutine]);

  const generateMutation = useMutation({
    mutationFn: (values: GenerateRoutineFormValues) => planningApi.generateRoutine(values),
    onSuccess: async (res) => {
      setSelectedRoutineId(res.data.id);
      setFeedbackBanner(
        "Draft routine generated. Review or customize slots below, then click Confirm & Save Schedule.",
      );
      await queryClient.invalidateQueries({ queryKey: ["routines", "list"] });
    },
  });

  const updateMutation = useMutation({
    mutationFn: (vars: {
      routineId: string;
      status?: "draft" | "confirmed" | "archived";
      activities?: RoutineActivityEditable[];
    }) =>
      planningApi.updateRoutine(vars.routineId, {
        status: vars.status,
        activities: vars.activities,
      }),
    onSuccess: async (res) => {
      setFeedbackBanner(
        res.data.status === "confirmed"
          ? "Schedule explicitly confirmed and saved."
          : "Routine slots updated and screened against snapshot AQI.",
      );
      setHasUnsavedEdits(false);
      await queryClient.invalidateQueries({ queryKey: ["routines", "list"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (routineId: string) => planningApi.deleteRoutine(routineId),
    onSuccess: async () => {
      setSelectedRoutineId(null);
      setFeedbackBanner("Routine deleted.");
      await queryClient.invalidateQueries({ queryKey: ["routines", "list"] });
    },
  });

  if (routinesQuery.isLoading) {
    return <WorkspaceSkeleton className="mt-6 h-64" />;
  }

  if (routinesQuery.isError) {
    return (
      <WorkspaceAuthOrErrorNotice
        error={routinesQuery.error}
        unauthPrompt="to generate, customize, and confirm personalized Morning–Night routines."
        errorMessage="Unable to load your saved routines."
        onRetry={() => void routinesQuery.refetch()}
      />
    );
  }

  const updateSlotField = <K extends keyof RoutineActivityEditable>(
    idx: number,
    key: K,
    value: RoutineActivityEditable[K],
  ) => {
    setEditedSlots((prev) =>
      prev.map((slot, i) => (i === idx ? { ...slot, [key]: value } : slot)),
    );
    setHasUnsavedEdits(true);
  };

  return (
    <div className="mt-6 space-y-6 text-text-primary">
      <GenerateRoutineFormCard
        form={form}
        isPending={generateMutation.isPending}
        onSubmit={(vals) => generateMutation.mutate(vals)}
      />

      {feedbackBanner ? (
        <div
          role="status"
          className="rounded-lg border border-brand-primary/60 bg-brand-accent/40 px-4 py-3 text-sm font-medium"
        >
          {feedbackBanner}
        </div>
      ) : null}

      <SavedRoutineSelectorBar
        routines={routines}
        activeRoutine={activeRoutine}
        hasUnsavedEdits={hasUnsavedEdits}
        updatePending={updateMutation.isPending}
        deletePending={deleteMutation.isPending}
        onSelectRoutine={setSelectedRoutineId}
        onSaveSlots={() => {
          if (activeRoutine) {
            updateMutation.mutate({ routineId: activeRoutine.id, activities: editedSlots });
          }
        }}
        onConfirmRoutine={() => {
          if (activeRoutine) {
            updateMutation.mutate({
              routineId: activeRoutine.id,
              status: "confirmed",
              activities: hasUnsavedEdits ? editedSlots : undefined,
            });
          }
        }}
        onDeleteRoutine={() => {
          if (activeRoutine) {
            deleteMutation.mutate(activeRoutine.id);
          }
        }}
      />

      {activeRoutine ? (
        <ActiveRoutineTimelineSection
          routine={activeRoutine}
          editedSlots={editedSlots}
          onUpdateSlotField={updateSlotField}
        />
      ) : null}
    </div>
  );
}
