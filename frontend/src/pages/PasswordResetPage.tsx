import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import { confirmPasswordReset } from "../api/auth";
import { ApiError } from "../api/client";

type Props = { onReset: () => void };
type FieldErrors = { new_password?: string[]; confirm_password?: string[] };

export function PasswordResetPage({ onReset }: Props) {
  const [credentials] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    return { uid: params.get("uid"), token: params.get("token") };
  });
  const [busy, setBusy] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});

  useEffect(() => {
    window.history.replaceState({}, "", "/reset-password");
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSuccess(null);
    setFieldErrors({});
    const form = event.currentTarget;
    const data = new FormData(form);
    const newPassword = String(data.get("new_password"));
    const confirmPassword = String(data.get("confirm_password"));
    if (newPassword !== confirmPassword) {
      setFieldErrors({ confirm_password: ["Passwords do not match."] });
      return;
    }
    if (!credentials.uid || !credentials.token) {
      setError("This password reset link is invalid or expired.");
      return;
    }
    setBusy(true);
    try {
      const result = await confirmPasswordReset(
        credentials.uid,
        credentials.token,
        newPassword,
        confirmPassword,
      );
      form.reset();
      onReset();
      setSuccess(result.detail);
    } catch (requestError) {
      if (requestError instanceof ApiError) {
        const nextErrors: FieldErrors = {};
        for (const field of ["new_password", "confirm_password"] as const) {
          const value = requestError.body[field];
          if (Array.isArray(value)) nextErrors[field] = value.filter((item): item is string => typeof item === "string");
        }
        if (Object.keys(nextErrors).length) {
          setFieldErrors(nextErrors);
        } else {
          setError("This password reset link is invalid or expired.");
        }
      } else {
        setError("Password reset is unavailable right now. Please try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-xl px-4 py-16">
      <section className="rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="text-2xl font-bold">Reset password</h1>
        {success ? (
          <>
            <p className="mt-4 text-emerald-700" role="status">{success}</p>
            <a className="mt-6 inline-block font-medium text-blue-700 underline" href="/">Return to login</a>
          </>
        ) : (
          <form className="mt-5 space-y-4" onSubmit={submit}>
            <label className="block text-sm font-medium" htmlFor="new-password">New password</label>
            <input aria-describedby={fieldErrors.new_password ? "new-password-errors" : undefined} className="w-full rounded-md border border-slate-300 px-3 py-2" id="new-password" name="new_password" required type="password" />
            {fieldErrors.new_password && <ul id="new-password-errors" role="alert">{fieldErrors.new_password.map((item) => <li key={item}>{item}</li>)}</ul>}
            <label className="block text-sm font-medium" htmlFor="confirm-password">Confirm password</label>
            <input aria-describedby={fieldErrors.confirm_password ? "confirm-password-errors" : undefined} className="w-full rounded-md border border-slate-300 px-3 py-2" id="confirm-password" name="confirm_password" required type="password" />
            {fieldErrors.confirm_password && <ul id="confirm-password-errors" role="alert">{fieldErrors.confirm_password.map((item) => <li key={item}>{item}</li>)}</ul>}
            <button className="rounded-md bg-blue-700 px-4 py-2 font-medium text-white disabled:opacity-60" disabled={busy} type="submit">{busy ? "Changing…" : "Change password"}</button>
          </form>
        )}
        {!success && <a className="mt-6 inline-block font-medium text-blue-700 underline" href="/">Cancel</a>}
        {error && <p className="mt-4 text-red-700" role="alert">{error}</p>}
      </section>
    </main>
  );
}
