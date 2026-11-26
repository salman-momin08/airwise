"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { GuidanceCard } from "@/components/assistant/guidance-card";
import { assistantApi } from "@/lib/api/assistant";
import { identityApi } from "@/lib/api/identity";
import { ApiClientError } from "@/lib/api/client";
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
      message: "", city: location.selectedCity, standard: location.aqiStandard,
      ai_consent: false, use_preferences: false,
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
      return assistantApi.stream(values, conversationId, (event) => {
        if (event.event === "status") setStage(event.data.tool ?? event.data.stage);
        if (event.event === "delta") setDelta((previous) => previous + event.data.content);
      }, controller.current.signal);
    },
    retry: false,
    onSuccess: async (response) => {
      setResult(response);
      setConversationId(response.conversation_id);
      setDelta("");
      form.resetField("message");
      await queryClient.invalidateQueries({ queryKey: ["assistant"] });
    },
    onSettled: () => { controller.current = null; },
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

  if (me.isLoading) return <p role="status" aria-busy="true">Loading assistant settings...</p>;
  if (me.isError) {
    const unauthenticated = me.error instanceof ApiClientError && me.error.status === 401;
    return <div role="alert">{unauthenticated
      ? <p>Please <Link className="text-brand-primary underline" href="/login">sign in</Link> to use the assistant.</p>
      : <><p>Assistant settings could not be loaded.</p>
        <button type="button" onClick={() => void me.refetch()}>Retry</button></>}</div>;
  }

  const errors = form.formState.errors;
  return (
    <div className="mt-6 space-y-5 text-text-primary">
      <p className="text-sm">Powered by Gemini with backend-verified environmental data.
        This is not a medical service. Seek urgent care for chest pain or severe breathing difficulty.</p>
      <p className="text-sm">
        Chat history is {me.data?.data.preferences.save_chat_history ? "saved to your account" : "not saved"}.
        Manage this in <Link className="text-brand-primary underline" href="/dashboard/settings/privacy">privacy settings</Link>.
      </p>
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm">Saved conversations
          <select className="ml-2 rounded border border-text-secondary bg-surface p-2"
            value={conversationId ?? ""} disabled={send.isPending || erase.isPending}
            onChange={(event) => { setConversationId(event.target.value || null); setResult(null); send.reset(); }}>
            <option value="">New conversation</option>
            {conversations.data?.data.map((conversation) =>
              <option key={conversation.id} value={conversation.id}>
                {new Date(conversation.created_at).toLocaleString()}
              </option>)}
          </select>
        </label>
        <button type="button" disabled={send.isPending || erase.isPending}
          className="rounded border border-text-secondary px-3 py-2 text-sm"
          onClick={() => setConfirmDelete(true)}>Delete chat history</button>
      </div>
      {confirmDelete && <div role="group" aria-label="Confirm history deletion" className="space-x-3 rounded border border-border p-3">
        <p>This permanently deletes all your saved conversations.</p>
        <button type="button" disabled={erase.isPending} onClick={() => erase.mutate()}>Confirm deletion</button>
        <button type="button" onClick={() => setConfirmDelete(false)}>Keep history</button>
      </div>}
      {(conversations.isError || messages.isError || erase.isError) &&
        <div role="alert"><p>Chat history could not be loaded or updated.</p>
          <button type="button" onClick={() => {
            if (erase.isError) erase.mutate();
            else { void conversations.refetch(); if (conversationId) void messages.refetch(); }
          }}>Retry history operation</button></div>}
      {messages.isFetching && <p role="status">Loading conversation...</p>}
      {!conversationId && !result && <p className="text-sm">Ask about exposure, indoor air or trusted pollution guidance. No readings will be guessed.</p>}
      <div className="space-y-4">
        {messages.data?.data.map((message) => message.structured_response
          ? <GuidanceCard key={message.id} guidance={message.structured_response} />
          : <p key={message.id} className="rounded border border-border p-3 text-sm"><strong>You:</strong> {message.content}</p>)}
        {result && (!result.message_id || !messages.data?.data.some((message) => message.id === result.message_id)) &&
          <GuidanceCard guidance={result.structured_response} />}
      </div>
      {result?.generation.is_fallback && <p role="status" className="text-sm">
        Safe guidance mode: {result.generation.fallback_reason}. No unverified model response was displayed.
      </p>}
      <div role="status" aria-live="polite" aria-atomic="true" className="text-sm">
        {send.isPending ? `Working: ${stage.replaceAll("_", " ")}` : cancelled ? "Response stopped." : ""}
      </div>
      {send.isPending && delta && <p aria-label="Validated response arriving" className="text-sm">{delta}</p>}
      {send.isError && !cancelled && <p role="alert" className="text-sm">
        {send.error instanceof Error ? send.error.message : "The assistant request failed. Please retry."}
      </p>}
      <form onSubmit={form.handleSubmit((values) => send.mutate(values))} className="space-y-4 rounded-card border border-border bg-surface p-5">
        <fieldset disabled={send.isPending || erase.isPending} className="space-y-4">
          <legend className="font-semibold">Ask AirWise Copilot</legend>
          <div className="flex flex-wrap gap-4">
            <label className="text-sm">City
              <input {...form.register("city")} aria-invalid={Boolean(errors.city)} aria-describedby="city-error"
                className="ml-2 rounded border border-text-secondary bg-surface p-2" />
            </label>
            <label className="text-sm">AQI standard
              <select {...form.register("standard")} className="ml-2 rounded border border-text-secondary bg-surface p-2">
                <option value="india_naqi">India NAQI</option><option value="us_epa">US EPA</option>
              </select>
            </label>
          </div>
          <p id="city-error" className="text-sm">{errors.city?.message}</p>
          <label htmlFor="assistant-question" className="block text-sm font-medium">Your environmental question</label>
          <textarea id="assistant-question" {...form.register("message")} rows={3} maxLength={2000}
            aria-invalid={Boolean(errors.message)} aria-describedby="question-help question-error"
            className="w-full rounded border border-text-secondary bg-surface p-3" />
          <p id="question-help" className="text-sm">Do not include names, account details, street addresses or exact coordinates.</p>
          <p id="question-error" className="text-sm">{errors.message?.message}</p>
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" {...form.register("ai_consent")} aria-invalid={Boolean(errors.ai_consent)} aria-describedby="consent-error" />
            I agree to send my minimized question and city-level context to Google Gemini to generate this response.
          </label>
          <p id="consent-error" className="text-sm">{errors.ai_consent?.message}</p>
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" {...form.register("use_preferences")} />
            Also use my saved purifier, budget and household sensitivity preferences for this request.
          </label>
          <button type="submit" className="rounded bg-brand-primary px-4 py-2 font-semibold text-white dark:text-background disabled:opacity-60">
            {send.isPending ? "Responding..." : "Send question"}
          </button>
        </fieldset>
      </form>
      {send.isPending && <button type="button" className="rounded border border-text-secondary px-4 py-2"
        onClick={() => { setCancelled(true); controller.current?.abort(); }}>Stop response</button>}
    </div>
  );
}
