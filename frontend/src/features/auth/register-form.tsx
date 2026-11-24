"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiClientError } from "@/lib/api/client";
import { identityApi } from "@/lib/api/identity";
import { registerSchema, type RegisterFormValues } from "@/lib/validation/identity";
import { useLocationStore } from "@/stores/location-store";

export function RegisterForm() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const setAqiStandard = useLocationStore((state) => state.setAqiStandard);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      display_name: "",
      email: "",
      password: "",
      preferred_aqi_standard: "india_naqi",
      timezone: "Asia/Kolkata",
    },
  });

  const registerMutation = useMutation({
    mutationFn: (values: RegisterFormValues) => identityApi.register(values),
    onSuccess: async (res) => {
      setAqiStandard(res.data.preferred_aqi_standard);
      await queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
      router.push("/dashboard/settings/locations");
    },
  });

  return (
    <section className="mt-6 max-w-lg rounded-card border border-border bg-surface p-6 shadow-sm">
      {registerMutation.isError ? (
        <div
          role="alert"
          className="mb-4 rounded-lg border border-red-400/60 bg-red-500/10 p-3 text-sm text-red-700 dark:text-red-300"
        >
          {registerMutation.error instanceof ApiClientError
            ? registerMutation.error.message
            : "Registration failed. Check your connection and try again."}
        </div>
      ) : null}

      <form
        onSubmit={handleSubmit((values) => registerMutation.mutate(values))}
        noValidate
        className="space-y-4"
      >
        <div>
          <label htmlFor="reg-name" className="block text-sm font-medium text-text-primary">
            Display name
          </label>
          <input
            id="reg-name"
            type="text"
            autoComplete="name"
            aria-invalid={Boolean(errors.display_name)}
            aria-describedby={errors.display_name ? "reg-name-error" : undefined}
            {...register("display_name")}
            className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-brand-primary"
          />
          {errors.display_name ? (
            <p id="reg-name-error" className="mt-1 text-xs text-red-600 dark:text-red-400">
              {errors.display_name.message}
            </p>
          ) : null}
        </div>

        <div>
          <label htmlFor="reg-email" className="block text-sm font-medium text-text-primary">
            Email address
          </label>
          <input
            id="reg-email"
            type="email"
            autoComplete="email"
            aria-invalid={Boolean(errors.email)}
            aria-describedby={errors.email ? "reg-email-error" : undefined}
            {...register("email")}
            className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-brand-primary"
          />
          {errors.email ? (
            <p id="reg-email-error" className="mt-1 text-xs text-red-600 dark:text-red-400">
              {errors.email.message}
            </p>
          ) : null}
        </div>

        <div>
          <label htmlFor="reg-password" className="block text-sm font-medium text-text-primary">
            Password (minimum 10 characters, letters &amp; numbers)
          </label>
          <input
            id="reg-password"
            type="password"
            autoComplete="new-password"
            aria-invalid={Boolean(errors.password)}
            aria-describedby={errors.password ? "reg-password-error" : undefined}
            {...register("password")}
            className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-brand-primary"
          />
          {errors.password ? (
            <p id="reg-password-error" className="mt-1 text-xs text-red-600 dark:text-red-400">
              {errors.password.message}
            </p>
          ) : null}
        </div>

        <div>
          <label htmlFor="reg-standard" className="block text-sm font-medium text-text-primary">
            Preferred AQI standard
          </label>
          <select
            id="reg-standard"
            {...register("preferred_aqi_standard")}
            className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-brand-primary"
          >
            <option value="india_naqi">India National AQI (CPCB NAQI)</option>
            <option value="us_epa">US EPA AQI</option>
          </select>
          <p className="mt-1 text-xs text-text-secondary">
            Standards use distinct breakpoints and categories and are never mixed.
          </p>
        </div>

        <button
          type="submit"
          disabled={registerMutation.isPending}
          className="w-full rounded-lg bg-brand-primary px-4 py-2.5 text-sm font-semibold text-white hover:opacity-95 disabled:opacity-60"
        >
          {registerMutation.isPending ? "Creating account…" : "Create account"}
        </button>
      </form>

      <p className="mt-4 text-center text-sm text-text-secondary">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-brand-primary underline">
          Sign in
        </Link>
      </p>
    </section>
  );
}
