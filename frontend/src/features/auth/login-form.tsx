"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiClientError } from "@/lib/api/client";
import { identityApi } from "@/lib/api/identity";
import { loginSchema, type LoginFormValues } from "@/lib/validation/identity";
import { useLocationStore } from "@/stores/location-store";

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const setAqiStandard = useLocationStore((state) => state.setAqiStandard);
  const [verificationMessage, setVerificationMessage] = useState<string | null>(null);

  const verifyToken = searchParams.get("verify_token");

  useEffect(() => {
    if (!verifyToken) return;
    let active = true;
    identityApi
      .verifyEmail(verifyToken)
      .then(() => {
        if (active) setVerificationMessage("Your email address has been verified.");
      })
      .catch((err: unknown) => {
        if (active) {
          setVerificationMessage(
            err instanceof ApiClientError
              ? err.message
              : "Unable to verify email token.",
          );
        }
      });
    return () => {
      active = false;
    };
  }, [verifyToken]);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  const loginMutation = useMutation({
    mutationFn: (values: LoginFormValues) => identityApi.login(values),
    onSuccess: async (res) => {
      setAqiStandard(res.data.preferred_aqi_standard);
      await queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
      router.push("/dashboard");
    },
  });

  return (
    <section className="mt-6 max-w-md rounded-card border border-border bg-surface p-6 shadow-sm">
      {verificationMessage ? (
        <div
          role="status"
          className="mb-4 rounded-lg border border-brand-secondary/40 bg-brand-accent/40 p-3 text-sm text-text-primary"
        >
          {verificationMessage}
        </div>
      ) : null}

      {loginMutation.isError ? (
        <div
          role="alert"
          className="mb-4 rounded-lg border border-red-400/60 bg-red-500/10 p-3 text-sm text-red-700 dark:text-red-300"
        >
          {loginMutation.error instanceof ApiClientError
            ? loginMutation.error.message
            : "Sign-in failed. Check your connection and try again."}
        </div>
      ) : null}

      <form
        onSubmit={handleSubmit((values) => loginMutation.mutate(values))}
        noValidate
        className="space-y-4"
      >
        <div>
          <label htmlFor="login-email" className="block text-sm font-medium text-text-primary">
            Email address
          </label>
          <input
            id="login-email"
            type="email"
            autoComplete="email"
            aria-invalid={Boolean(errors.email)}
            aria-describedby={errors.email ? "login-email-error" : undefined}
            {...register("email")}
            className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-brand-primary"
          />
          {errors.email ? (
            <p id="login-email-error" className="mt-1 text-xs text-red-600 dark:text-red-400">
              {errors.email.message}
            </p>
          ) : null}
        </div>

        <div>
          <div className="flex items-center justify-between">
            <label htmlFor="login-password" className="block text-sm font-medium text-text-primary">
              Password
            </label>
            <Link href="/forgot-password" className="text-xs font-medium text-brand-primary underline">
              Forgot password?
            </Link>
          </div>
          <input
            id="login-password"
            type="password"
            autoComplete="current-password"
            aria-invalid={Boolean(errors.password)}
            aria-describedby={errors.password ? "login-password-error" : undefined}
            {...register("password")}
            className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-brand-primary"
          />
          {errors.password ? (
            <p id="login-password-error" className="mt-1 text-xs text-red-600 dark:text-red-400">
              {errors.password.message}
            </p>
          ) : null}
        </div>

        <button
          type="submit"
          disabled={loginMutation.isPending}
          className="w-full rounded-lg bg-brand-primary px-4 py-2.5 text-sm font-semibold text-white hover:opacity-95 disabled:opacity-60 dark:text-background"
        >
          {loginMutation.isPending ? "Signing in…" : "Sign in"}
        </button>
      </form>

      <p className="mt-4 text-center text-sm text-text-secondary">
        New to AirWise AI?{" "}
        <Link href="/register" className="font-medium text-brand-primary underline">
          Create an account
        </Link>{" "}
        or{" "}
        <Link href="/air-quality" className="font-medium text-brand-primary underline">
          browse public AQI as a guest
        </Link>
        .
      </p>
    </section>
  );
}
