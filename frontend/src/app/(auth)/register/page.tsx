import { RegisterForm } from "@/features/auth/register-form";

export default function RegisterPage() {
  return (
    <main id="main-content" className="mx-auto max-w-5xl px-6 py-12">
      <h1 className="text-2xl font-bold text-text-primary">Create Account</h1>
      <p className="mt-2 text-sm text-text-secondary">
        Create an AirWise AI account to save coarse-by-default locations, household routines, and
        smart smog alerts.
      </p>
      <RegisterForm />
    </main>
  );
}
