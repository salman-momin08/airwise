"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useForm, type UseFormReturn } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { GuidanceCard } from "@/components/assistant/guidance-card";
import { WorkspaceAuthOrErrorNotice } from "@/components/ui/workspace-state";
import { assistantApi } from "@/lib/api/assistant";
import { identityApi } from "@/lib/api/identity";
import { chatFormSchema, type ChatFormValues } from "@/lib/validation/assistant";
import { useLocationStore } from "@/stores/location-store";
import type { ChatMessage, ChatResult, Conversation } from "@/types/assistant";

interface HistoryControlsProps {
  conversations: Conversation[];
  conversationId: string | null;
  disabled: boolean;
  confirmDelete: boolean;
  erasePending: boolean;
  onSelectConversation: (nextId: string | null) => void;
  onPromptDelete: () => void;
  onConfirmDelete: () => void;
  onCancelDelete: () => void;
}

function AssistantHistoryControls({
  conversations,
  conversationId,
  disabled,
  confirmDelete,
  erasePending,
  onSelectConversation,
  onPromptDelete,
  onConfirmDelete,
  onCancelDelete,
}: HistoryControlsProps) {
  return (
    <>
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm">
          Saved conversations
          <select
            className="ml-2 rounded border border-text-secondary bg-surface p-2"
            value={conversationId ?? ""}
            disabled={disabled}
            onChange={(event) => onSelectConversation(event.target.value || null)}
          >
            <option value="">New conversation</option>
            {conversations.map((conversation) => (
              <option key={conversation.id} value={conversation.id}>
                {new Date(conversation.created_at).toLocaleString()}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          disabled={disabled}
          className="rounded border border-text-secondary px-3 py-2 text-sm"
          onClick={onPromptDelete}
        >
          Delete chat history
        </button>
      </div>

      {confirmDelete ? (
        <div
          role="group"
          aria-label="Confirm history deletion"
          className="space-x-3 rounded border border-border p-3"
        >
          <p>This permanently deletes all your saved conversations.</p>
          <button type="button" disabled={erasePending} onClick={onConfirmDelete}>
            Confirm deletion
          </button>
          <button type="button" onClick={onCancelDelete}>
            Keep history
          </button>
        </div>
      ) : null}
    </>
  );
}

function AssistantConversationFeed({
  conversationId,
  messages,
  result,
  isFetchingMessages,
}: {
  conversationId: string | null;
  messages: ChatMessage[];
  result: ChatResult | null;
  isFetchingMessages: boolean;
}) {
  const showUnsavedResult =
    result !== null &&
    (!result.message_id || !messages.some((message) => message.id === result.message_id));

  return (
    <>
      {isFetchingMessages ? <p role="status">Loading conversation...</p> : null}
      {!conversationId && !result ? (
        <p className="text-sm">
          Ask about exposure, indoor air or trusted pollution guidance. No readings will be
          guessed.
        </p>
      ) : null}
      <div className="space-y-4">
        {messages.map((message) =>
          message.structured_response ? (
            <GuidanceCard key={message.id} guidance={message.structured_response} />
          ) : (
            <p key={message.id} className="rounded border border-border p-3 text-sm">
              <strong>You:</strong> {message.content}
            </p>
          ),
        )}
        {showUnsavedResult ? <GuidanceCard guidance={result.structured_response} /> : null}
      </div>
      {result?.generation.is_fallback ? (
        <p role="status" className="text-sm">
          Safe guidance mode: {result.generation.fallback_reason}. No unverified model response was
          displayed.
        </p>
      ) : null}
    </>
  );
}

function AssistantPromptForm({
  form,
  isPending,
  disabled,
  onSubmit,
}: {
  form: UseFormReturn<ChatFormValues>;
  isPending: boolean;
  disabled: boolean;
  onSubmit: (values: ChatFormValues) => void;
}) {
  const errors = form.formState.errors;
  return (
    <form
      onSubmit={form.handleSubmit(onSubmit)}
      className="space-y-4 rounded-card border border-border bg-surface p-5"
    >
      <fieldset disabled={disabled} className="space-y-4">
        <legend className="font-semibold">Ask AirWise Copilot</legend>
        <div className="flex flex-wrap gap-4">
          <label className="text-sm">
            City
            <input
              {...form.register("city")}
              aria-invalid={Boolean(errors.city)}
              aria-describedby="city-error"
              className="ml-2 rounded border border-text-secondary bg-surface p-2"
            />
          </label>
          <label className="text-sm">
            AQI standard
            <select
              {...form.register("standard")}
              className="ml-2 rounded border border-text-secondary bg-surface p-2"
            >
              <option value="india_naqi">India NAQI</option>
              <option value="us_epa">US EPA</option>
            </select>
          </label>
        </div>
        <p id="city-error" className="text-sm">
          {errors.city?.message}
        </p>

        <label htmlFor="assistant-question" className="block text-sm font-medium">
          Your environmental question
        </label>
        <textarea
          id="assistant-question"
          {...form.register("message")}
          rows={3}
          maxLength={2000}
          aria-invalid={Boolean(errors.message)}
          aria-describedby="question-help question-error"
          className="w-full rounded border border-text-secondary bg-surface p-3"
        />
        <p id="question-help" className="text-sm">
          Do not include names, account details, street addresses or exact coordinates.
        </p>
        <p id="question-error" className="text-sm">
          {errors.message?.message}
        </p>

        <label className="flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            {...form.register("ai_consent")}
            aria-invalid={Boolean(errors.ai_consent)}
            aria-describedby="consent-error"
          />
          I agree to send my minimized question and city-level context to Google Gemini to generate
          this response.
        </label>
        <p id="consent-error" className="text-sm">
          {errors.ai_consent?.message}
        </p>

        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" {...form.register("use_preferences")} />
          Also use my saved purifier, budget and household sensitivity preferences for this request.
        </label>

        <button
          type="submit"
          className="rounded bg-brand-primary px-4 py-2 font-semibold text-white disabled:opacity-60 dark:text-background"
        >
          {isPending ? "Responding..." : "Send question"}
        </button>
      </fieldset>
    </form>
  );
}

function AssistantStreamingFeedback({
  isPending,
  stage,
  cancelled,
  delta,
  isError,
  error,
  onStop,
}: {
  isPending: boolean;
  stage: string;
  cancelled: boolean;
  delta: string;
  isError: boolean;
  error: unknown;
  onStop: () => void;
}) {
  let liveStatusText = "";
  if (isPending) {
    liveStatusText = `Working: ${stage.replaceAll("_", " ")}`;
  } else if (cancelled) {
    liveStatusText = "Response stopped.";
  }

  const sendFailureText =
    error instanceof Error ? error.message : "The assistant request failed. Please retry.";

  return (
    <>
      <div role="status" aria-live="polite" aria-atomic="true" className="text-sm">
        {liveStatusText}
      </div>
      {isPending && delta ? (
        <p aria-label="Validated response arriving" className="text-sm">
          {delta}
        </p>
      ) : null}
      {isError && !cancelled ? (
        <p role="alert" className="text-sm">
          {sendFailureText}
        </p>
      ) : null}
      {isPending ? (
        <button
          type="button"
          className="rounded border border-text-secondary px-4 py-2"
          onClick={onStop}
        >
          Stop response
        </button>
      ) : null}
    </>
  );
}

function AssistantHistoryErrorAlert({
  hasError,
  eraseError,
  conversationId,
  onRetryErase,
  onRefetchConversations,
  onRefetchMessages,
}: {
  hasError: boolean;
  eraseError: boolean;
  conversationId: string | null;
  onRetryErase: () => void;
  onRefetchConversations: () => void;
  onRefetchMessages: () => void;
}) {
  if (!hasError) return null;
  const handleRetry = () => {
    if (eraseError) {
      onRetryErase();
      return;
    }
    onRefetchConversations();
    if (conversationId) {
      onRefetchMessages();
    }
  };
  return (
    <div role="alert">
      <p>Chat history could not be loaded or updated.</p>
      <button type="button" onClick={handleRetry}>
        Retry history operation
      </button>
    </div>
  );
}
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
