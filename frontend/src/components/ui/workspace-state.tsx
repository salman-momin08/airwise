import Link from "next/link";
import { ApiClientError } from "@/lib/api/client";

interface WorkspaceSkeletonProps {
  className?: string;
}

export function WorkspaceSkeleton({
  className = "mt-6 h-56",
}: WorkspaceSkeletonProps) {
  return (
    <div
      aria-busy="true"
      className={`animate-pulse rounded-card border border-border bg-surface p-6 ${className}`}
    />
  );
}

interface WorkspaceAuthOrErrorNoticeProps {
  error: unknown;
  unauthPrompt: string;
  errorMessage: string;
  onRetry?: () => void;
  retryLabel?: string;
  className?: string;
}

export function WorkspaceAuthOrErrorNotice({
  error,
  unauthPrompt,
  errorMessage,
  onRetry,
  retryLabel = "Retry",
  className = "mt-6",
}: WorkspaceAuthOrErrorNoticeProps) {
  const isUnauthenticated =
    error instanceof ApiClientError && error.status === 401;

  return (
    <div
      role="alert"
      className={`rounded-card border border-border bg-surface p-6 text-sm text-text-primary ${className}`}
    >
      {isUnauthenticated ? (
        <p>
          Please{" "}
          <Link href="/login" className="font-semibold text-brand-primary underline">
            sign in
          </Link>{" "}
          {unauthPrompt}
        </p>
      ) : (
        <div className="space-y-3">
          <p>{errorMessage}</p>
          {onRetry ? (
            <button
              type="button"
              onClick={onRetry}
              className="rounded border border-text-secondary px-3 py-1.5 font-medium"
            >
              {retryLabel}
            </button>
          ) : null}
        </div>
      )}
    </div>
  );
}
