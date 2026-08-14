import { useState } from "react";
import type { FormEvent } from "react";

import { resendVerification } from "../api/auth";
import { ApiError } from "../api/client";

type ResendVerificationFormProps = {
  initialEmail?: string;
};

export function ResendVerificationForm({ initialEmail = "" }: ResendVerificationFormProps) {
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    setError(null);
    const email = String(new FormData(event.currentTarget).get("resend-email"));
    try {
      const result = await resendVerification(email);
      setMessage(result.detail);
    } catch (requestError) {
      const detail = requestError instanceof ApiError && typeof requestError.body.detail === "string"
        ? requestError.body.detail
        : null;
      setError(detail ?? "Unable to request another verification email. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="mt-5 border-t border-slate-200 pt-5" onSubmit={submit}>
      <label className="block text-sm font-medium" htmlFor="resend-verification-email">
        Email address
      </label>
      <input
        className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
        defaultValue={initialEmail}
        id="resend-verification-email"
        name="resend-email"
        required
        type="email"
      />
      <button
        className="mt-3 rounded-md border border-blue-700 px-4 py-2 text-sm font-medium text-blue-700 disabled:opacity-60"
        disabled={busy}
        type="submit"
      >
        {busy ? "Requesting…" : "Resend verification email"}
      </button>
      {message && <p className="mt-3 text-sm text-emerald-700" role="status">{message}</p>}
      {error && <p className="mt-3 text-sm text-red-700" role="alert">{error}</p>}
    </form>
  );
}
