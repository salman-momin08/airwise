/**
 * Unit, UI, and `axe-core` accessibility tests for `apiRequest`, Zustand location store,
 * `WorkspaceSkeleton` / `WorkspaceAuthOrErrorNotice`, and Next.js App Router error/404 boundaries.
 */

import React from "react";
import axe from "axe-core";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import AppErrorBoundary from "@/app/error";
import NotFoundPage from "@/app/not-found";
import DashboardErrorBoundary from "@/app/(dashboard)/dashboard/error";
import AdminErrorBoundary from "@/app/admin/error";
import {
  WorkspaceAuthOrErrorNotice,
  WorkspaceSkeleton,
} from "@/components/ui/workspace-state";
import { ApiClientError, apiFetch, apiRequest } from "@/lib/api/client";
import { useLocationStore } from "@/stores/location-store";

describe("API Client, Location Store, and App Router Boundaries", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    document.cookie = "airwise_csrf=; Max-Age=0; path=/";
    useLocationStore.setState({ selectedCity: "Delhi", aqiStandard: "india_naqi" });
  });

  it("injects X-CSRF-Token on mutations, preserves = in cookie values, and omits CSRF on GET", async () => {
    document.cookie = "airwise_csrf=csrf-token-with%3Dpadding==";
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          data: { ok: true },
          meta: { request_id: "req-1", timestamp: "2026-11-27T00:00:00Z" },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    await apiRequest<{ ok: boolean }>("/users/me", {
      method: "PATCH",
      body: JSON.stringify({ display_name: "Asha" }),
    });

    const patchCall = fetchSpy.mock.calls[0];
    const patchHeaders = patchCall?.[1]?.headers as Headers;
    expect(patchHeaders.get("X-CSRF-Token")).toBe("csrf-token-with=padding==");
    expect(patchHeaders.get("Content-Type")).toBe("application/json");

    await apiFetch("/air-quality/current?city=Delhi");
    const getHeaders = fetchSpy.mock.calls[1]?.[1]?.headers as Headers;
    expect(getHeaders.get("X-CSRF-Token")).toBeNull();
    expect(getHeaders.get("Content-Type")).toBeNull();

    const formData = new FormData();
    formData.append("note", "clean");
    await apiFetch("/users/me", { method: "POST", body: formData });
    const formHeaders = fetchSpy.mock.calls[2]?.[1]?.headers as Headers;
    expect(formHeaders.get("Content-Type")).toBeNull();
    expect(formHeaders.get("X-CSRF-Token")).toBe("csrf-token-with=padding==");
  });

  it("parses structured ApiErrorEnvelope and falls back cleanly on non-JSON upstream errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          error: {
            code: "AIR_QUALITY_PROVIDER_UNAVAILABLE",
            message: "Station telemetry unavailable.",
            request_id: "req-503",
          },
        }),
        { status: 503, headers: { "Content-Type": "application/json" } },
      ),
    );

    await expect(apiRequest("/air-quality/current")).rejects.toMatchObject({
      name: "ApiClientError",
      code: "AIR_QUALITY_PROVIDER_UNAVAILABLE",
      message: "Station telemetry unavailable.",
      requestId: "req-503",
      status: 503,
    });

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response("Bad Gateway", {
        status: 502,
        headers: { "Content-Type": "text/plain" },
      }),
    );

    await expect(apiRequest("/air-quality/current")).rejects.toMatchObject({
      code: "HTTP_REQUEST_FAILED",
      status: 502,
      requestId: "unknown",
    });
  });

  it("updates active city and AQI standard in Zustand useLocationStore", () => {
    useLocationStore.getState().setSelectedCity("Bengaluru");
    useLocationStore.getState().setAqiStandard("us_epa");
    expect(useLocationStore.getState().selectedCity).toBe("Bengaluru");
    expect(useLocationStore.getState().aqiStandard).toBe("us_epa");
  });

  it("renders accessible WorkspaceSkeleton, WorkspaceAuthOrErrorNotice, ErrorBoundaries, and NotFoundPage with zero axe violations", async () => {
    const onReset = vi.fn();
    const onRetry = vi.fn();
    const testError = Object.assign(new Error("Render boom"), { digest: "dig-42" });

    const { container } = render(
      <div>
        <WorkspaceSkeleton label="Loading verified station data..." />
        <WorkspaceAuthOrErrorNotice
          error={new ApiClientError("AUTH_REQUIRED", "Sign in", "req-1", 401)}
          unauthPrompt="to view routines."
          errorMessage="Fallback error"
        />
        <WorkspaceAuthOrErrorNotice
          error={new Error("Network down")}
          unauthPrompt="to view routines."
          errorMessage="Network temporarily unreachable."
          onRetry={onRetry}
        />
        <AppErrorBoundary error={testError} reset={onReset} />
      </div>,
    );

    expect(screen.getByText("Loading verified station data...")).toBeInTheDocument();
    expect(screen.getByText(/Reference ID: dig-42/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onReset).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledTimes(1);

    const axeOptions = { rules: { "color-contrast": { enabled: false } } };

    cleanup();
    const dash = render(<DashboardErrorBoundary error={testError} reset={onReset} />);
    const dashAxe = await axe.run(dash.container, axeOptions);
    expect(dashAxe.violations).toHaveLength(0);

    cleanup();
    const adm = render(<AdminErrorBoundary error={testError} reset={onReset} />);
    const admAxe = await axe.run(adm.container, axeOptions);
    expect(admAxe.violations).toHaveLength(0);

    cleanup();
    const nf = render(<NotFoundPage />);
    expect(screen.getByRole("heading", { name: "Page not found" })).toBeInTheDocument();
    const nfAxe = await axe.run(nf.container, axeOptions);
    expect(nfAxe.violations).toHaveLength(0);
    expect(container).toBeDefined();
  });
});
