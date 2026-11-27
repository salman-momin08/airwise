import { Suspense } from "react";
import { PasswordRecoveryPanel } from "@/features/auth/password-recovery-panel";

export default function ForgotPasswordPage() {
  return (
    <main id="main-content" className="mx-auto max-w-5xl px-6 py-12">
      <h1 className="text-2xl font-bold text-text-primary">Reset Password</h1>
      <p className="mt-2 text-sm text-text-secondary">
        Request a single-use password reset link or set a new password using a valid reset token.
      </p>
      <Suspense fallback={<div aria-busy="true" className="mt-6 h-44 max-w-md animate-pulse rounded-card bg-surface" />}>
        <PasswordRecoveryPanel />
      </Suspense>
    </main>
  );
}
