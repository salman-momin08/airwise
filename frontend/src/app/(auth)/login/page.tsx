import { Suspense } from "react";
import { LoginForm } from "@/features/auth/login-form";

export default function LoginPage() {
  return (
    <main id="main-content" className="mx-auto max-w-5xl px-6 py-12">
      <h1 className="text-2xl font-bold text-text-primary">Sign In</h1>
      <p className="mt-2 text-sm text-text-secondary">
        Secure session sign-in using Argon2id password verification, HttpOnly cookies, and CSRF
        protection.
      </p>
      <Suspense fallback={<div aria-busy="true" className="mt-6 h-56 max-w-md animate-pulse rounded-card bg-surface" />}>
        <LoginForm />
      </Suspense>
    </main>
  );
}