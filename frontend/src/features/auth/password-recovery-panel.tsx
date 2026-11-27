"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { ApiClientError } from "@/lib/api/client";
import { identityApi } from "@/lib/api/identity";
import {
  forgotPasswordSchema,
  resetPasswordSchema,
  type ForgotPasswordFormValues,
  type ResetPasswordFormValues,
} from "@/lib/validation/identity";

function ResetPasswordWithTokenCard({ resetToken }: { resetToken: string }) {
  const [resetSuccess, setResetSuccess] = useState(false);
  const resetForm = useForm<ResetPasswordFormValues>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { token: resetToken, new_password: "" },
  });

  const resetMutation = useMutation({
    mutationFn: (values: ResetPasswordFormValues) => identityApi.resetPassword(values),
    onSuccess: () => setResetSuccess(true),
  });

  if (resetSuccess) {
    return (
      <section className="mt-6 max-w-md rounded-card border border-border bg-surface p-6 shadow-sm">
        <div role="status" className="space-y-3 text-sm text-text-primary">
          <p className="font-semibold text-emerald-800 dark:text-emerald-300">
            Password updated and previous sessions revoked.
          </p>
          <Link
            href="/login"
            className="inline-block rounded-lg bg-brand-primary px-4 py-2 font-medium text-white dark:text-background"
          >
            Sign in with new password
          </Link>
        </div>
      </section>
    );
  }

  const passwordError = resetForm.formState.errors.new_password;
  const resetErrorText =
    resetMutation.error instanceof ApiClientError
      ? resetMutation.error.message
      : "Unable to reset password.";

  return (
    <section className="mt-6 max-w-md rounded-card border border-border bg-surface p-6 shadow-sm">
      <form
        onSubmit={resetForm.handleSubmit((values) =>
          resetMutation.mutate({ ...values, token: resetToken }),
        )}
        noValidate
        className="space-y-4"
      >
        {resetMutation.isError ? (
          <div
            role="alert"
            className="rounded-lg border border-red-400/60 bg-red-500/10 p-3 text-sm text-red-700 dark:text-red-300"
          >
            {resetErrorText}
          </div>
        ) : null}

        <input type="hidden" value={resetToken} {...resetForm.register("token")} />

        <div>
          <label htmlFor="new-password" className="block text-sm font-medium text-text-primary">
            New password
          </label>
          <input
            id="new-password"
            type="password"
            autoComplete="new-password"
            aria-invalid={Boolean(passwordError)}
            aria-describedby={passwordError ? "new-password-error" : undefined}
            {...resetForm.register("new_password")}
            className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-brand-primary"
          />
          {passwordError ? (
            <p id="new-password-error" className="mt-1 text-xs text-red-600 dark:text-red-400">
              {passwordError.message}
            </p>
          ) : null}
        </div>

        <button
          type="submit"
          disabled={resetMutation.isPending}
          className="w-full rounded-lg bg-brand-primary px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60 dark:text-background"
        >
          {resetMutation.isPending ? "Updating password…" : "Update password"}
        </button>
      </form>
    </section>
  );
}

export function PasswordRecoveryPanel() {
  const searchParams = useSearchParams();
  const resetToken = searchParams.get("token");
  const [requestSentMessage, setRequestSentMessage] = useState<string | null>(null);

  const forgotForm = useForm<ForgotPasswordFormValues>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: { email: "" },
  });

  const forgotMutation = useMutation({
    mutationFn: (values: ForgotPasswordFormValues) => identityApi.forgotPassword(values),
    onSuccess: (res) => setRequestSentMessage(res.data.message),
  });

  if (resetToken) {
    return <ResetPasswordWithTokenCard resetToken={resetToken} />;
  }

  const emailError = forgotForm.formState.errors.email;
  const forgotErrorText =
    forgotMutation.error instanceof ApiClientError
      ? forgotMutation.error.message
      : "Unable to request reset link right now.";

  return (
    <section className="mt-6 max-w-md rounded-card border border-border bg-surface p-6 shadow-sm">
      {requestSentMessage ? (
        <div
          role="status"
          className="mb-4 rounded-lg border border-brand-secondary/40 bg-brand-accent/40 p-3 text-sm text-text-primary"
        >
          {requestSentMessage}
        </div>
      ) : null}

      {forgotMutation.isError ? (
        <div
          role="alert"
          className="mb-4 rounded-lg border border-red-400/60 bg-red-500/10 p-3 text-sm text-red-700 dark:text-red-300"
        >
          {forgotErrorText}
        </div>
      ) : null}

      <form
        onSubmit={forgotForm.handleSubmit((values) => forgotMutation.mutate(values))}
        noValidate
        className="space-y-4"
      >
        <div>
          <label htmlFor="forgot-email" className="block text-sm font-medium text-text-primary">
            Account email address
          </label>
          <input
            id="forgot-email"
            type="email"
            autoComplete="email"
            aria-invalid={Boolean(emailError)}
            aria-describedby={emailError ? "forgot-email-error" : undefined}
            {...forgotForm.register("email")}
            className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-brand-primary"
          />
          {emailError ? (
            <p id="forgot-email-error" className="mt-1 text-xs text-red-600 dark:text-red-400">
              {emailError.message}
            </p>
          ) : null}
        </div>

        <button
          type="submit"
          disabled={forgotMutation.isPending}
          className="w-full rounded-lg bg-brand-primary px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60 dark:text-background"
        >
          {forgotMutation.isPending ? "Sending link…" : "Send single-use reset link"}
        </button>
      </form>

      <p className="mt-4 text-center text-sm text-text-secondary">
        Remembered your password?{" "}
        <Link href="/login" className="font-medium text-brand-primary underline">
          Back to sign in
        </Link>
      </p>
    </section>
  );
}
