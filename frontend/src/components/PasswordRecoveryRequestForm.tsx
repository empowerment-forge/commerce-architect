import { useState } from "react";
import type { FormEvent } from "react";

import { requestPasswordReset } from "../api/auth";
import { ApiError } from "../api/client";

type Props = { onCancel: () => void };

export function PasswordRecoveryRequestForm({ onCancel }: Props) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    setError(null);
    const form = event.currentTarget;
    const email = String(new FormData(form).get("email"));
    try {
      const result = await requestPasswordReset(email);
      setMessage(result.detail);
      form.reset();
    } catch (requestError) {
      const emailErrors = requestError instanceof ApiError
        ? requestError.body.email
        : null;
      setError(
        Array.isArray(emailErrors) && typeof emailErrors[0] === "string"
          ? emailErrors[0]
          : "Password recovery is unavailable right now. Please try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-xl font-semibold">Reset your password</h2>
      <p className="mt-2 text-sm text-slate-600">Enter your account email address.</p>
      <form className="mt-4 space-y-4" onSubmit={submit}>
        <label className="block text-sm font-medium" htmlFor="recovery-email">
          Email
        </label>
        <input className="w-full rounded-md border border-slate-300 px-3 py-2" id="recovery-email" name="email" required type="email" />
        <div className="flex gap-3">
          <button className="rounded-md bg-blue-700 px-4 py-2 font-medium text-white disabled:opacity-60" disabled={busy} type="submit">
            {busy ? "Sending…" : "Send recovery email"}
          </button>
          <button className="rounded-md border border-slate-300 px-4 py-2 font-medium" onClick={onCancel} type="button">Back to login</button>
        </div>
      </form>
      {message && <p className="mt-4 text-sm text-emerald-700" role="status">{message}</p>}
      {error && <p className="mt-4 text-sm text-red-700" role="alert">{error}</p>}
    </section>
  );
}
