"use client";

/**
 * Stateful AirWise Copilot workspace managing SSE chat streaming, history, and erasure.
 */

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { WorkspaceAuthOrErrorNotice } from "@/components/ui/workspace-state";
import {
  AssistantConversationFeed,
  AssistantHistoryControls,
  AssistantHistoryErrorAlert,
  AssistantPromptForm,
  AssistantStreamingFeedback,
} from "@/features/assistant/assistant-workspace-sections";
import { assistantApi } from "@/lib/api/assistant";
import { identityApi } from "@/lib/api/identity";
import { chatFormSchema, type ChatFormValues } from "@/lib/validation/assistant";
import { useLocationStore } from "@/stores/location-store";
import type { ChatResult } from "@/types/assistant";

export function AssistantWorkspace() {
  const queryClient = useQueryClient();
  const location = useLocationStore();
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [result, setResult] = useState<ChatResult | null>(null);
  const [delta, setDelta] = useState("");
  const [stage, setStage] = useState("");
  const [cancelled, setCancelled] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const controller = useRef<AbortController | null>(null);

  const me = useQuery({
    queryKey: ["users", "me"],
    queryFn: () => identityApi.getUserProfileAndPreferences(),
    retry: false,
  });
  const conversations = useQuery({
    queryKey: ["assistant", "conversations"],
    queryFn: assistantApi.listConversations,
    enabled: me.isSuccess,
  });
  const messages = useQuery({
    queryKey: ["assistant", "messages", conversationId],
    queryFn: () => {
      if (!conversationId) throw new Error("Select a conversation first.");
      return assistantApi.messages(conversationId);
    },
    enabled: me.isSuccess && conversationId !== null,
  });

  const form = useForm<ChatFormValues>({
    resolver: zodResolver(chatFormSchema),
    defaultValues: {
      message: "",
      city: location.selectedCity,
      standard: location.aqiStandard,
      ai_consent: false,
      use_preferences: false,
    },
  });

  useEffect(() => () => controller.current?.abort(), []);

  const send = useMutation({
    mutationFn: async (values: ChatFormValues) => {
      controller.current = new AbortController();
      setCancelled(false);
      setDelta("");
      setResult(null);
      setStage("Connecting");
      return assistantApi.stream(
        values,
        conversationId,
        (event) => {
          if (event.event === "status") setStage(event.data.tool ?? event.data.stage);
          if (event.event === "delta") setDelta((previous) => previous + event.data.content);
        },
        controller.current.signal,
      );
    },
    retry: false,
    onSuccess: async (response) => {
      setResult(response);
      setConversationId(response.conversation_id);
      setDelta("");
      form.resetField("message");
      await queryClient.invalidateQueries({ queryKey: ["assistant"] });
    },
    onSettled: () => {
      controller.current = null;
    },
  });

  const erase = useMutation({
    mutationFn: assistantApi.deleteHistory,
    onSuccess: async () => {
      setConversationId(null);
      setResult(null);
      setConfirmDelete(false);
      queryClient.removeQueries({ queryKey: ["assistant", "messages"] });
      await queryClient.invalidateQueries({ queryKey: ["assistant", "conversations"] });
    },
  });

  if (me.isLoading) {
    return (
      <p role="status" aria-busy="true">
        Loading assistant settings...
      </p>
    );
  }
  if (me.isError || !me.data) {
    return (
      <WorkspaceAuthOrErrorNotice
        error={me.error}
        unauthPrompt="to use the assistant."
        errorMessage="Assistant settings could not be loaded."
        onRetry={() => void me.refetch()}
      />
    );
  }

  const retentionLabel = me.data.data.preferences.save_chat_history
    ? "saved to your account"
    : "not saved";
  const isBusy = send.isPending || erase.isPending;
  const conversationItems = conversations.data ? conversations.data.data : [];
  const messageItems = messages.data ? messages.data.data : [];
  const hasHistoryError = Boolean(
    conversations.isError || messages.isError || erase.isError,
  );

  return (
    <div className="mt-6 space-y-5 text-text-primary">
      <p className="text-sm">
        Powered by Gemini with backend-verified environmental data. This is not a medical service.
        Seek urgent care for chest pain or severe breathing difficulty.
      </p>
      <p className="text-sm">
        Chat history is {retentionLabel}. Manage this in{" "}
        <Link className="text-brand-primary underline" href="/dashboard/settings/privacy">
          privacy settings
        </Link>
        .
      </p>

      <AssistantHistoryControls
        conversations={conversationItems}
        conversationId={conversationId}
        disabled={isBusy}
        confirmDelete={confirmDelete}
        erasePending={erase.isPending}
        onSelectConversation={(nextId) => {
          setConversationId(nextId);
          setResult(null);
          send.reset();
        }}
        onPromptDelete={() => setConfirmDelete(true)}
        onConfirmDelete={() => erase.mutate()}
        onCancelDelete={() => setConfirmDelete(false)}
      />

      <AssistantHistoryErrorAlert
        hasError={hasHistoryError}
        eraseError={erase.isError}
        conversationId={conversationId}
        onRetryErase={() => erase.mutate()}
        onRefetchConversations={() => void conversations.refetch()}
        onRefetchMessages={() => void messages.refetch()}
      />

      <AssistantConversationFeed
        conversationId={conversationId}
        messages={messageItems}
        result={result}
        isFetchingMessages={messages.isFetching}
      />

      <AssistantPromptForm
        form={form}
        isPending={send.isPending}
        disabled={isBusy}
        onSubmit={(values) => send.mutate(values)}
      />

      <AssistantStreamingFeedback
        isPending={send.isPending}
        stage={stage}
        cancelled={cancelled}
        delta={delta}
        isError={send.isError}
        error={send.error}
        onStop={() => {
          setCancelled(true);
          controller.current?.abort();
        }}
      />
    </div>
  );
}
