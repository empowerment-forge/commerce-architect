import { useState } from "react";
import type { FormEvent } from "react";

import { resendVerification } from "../api/auth";
import { ApiError } from "../api/client";

type ResendVerificationFormProps = {
  collapsed?: boolean;
  initialEmail?: string;
  onCancel?: () => void;
};

export function ResendVerificationForm({
  collapsed = false,
  initialEmail = "",
  onCancel,
}: ResendVerificationFormProps) {
  const [open, setOpen] = useState(!collapsed);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function cancel() {
    setMessage(null);
    setError(null);
    if (collapsed) setOpen(false);
    onCancel?.();
  }

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

  if (!open) {
    return (
      <button
        className="mt-4 text-sm font-medium text-blue-700 underline"
        onClick={() => setOpen(true)}
        type="button"
      >
        Didn&apos;t receive the email? Resend verification
      </button>
    );
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
      <div className="mt-3 flex gap-3">
        <button
          className="rounded-md border border-blue-700 px-4 py-2 text-sm font-medium text-blue-700 disabled:opacity-60"
          disabled={busy}
          type="submit"
        >
          {busy ? "Requesting…" : "Resend verification email"}
        </button>
        {(collapsed || onCancel) && (
          <button className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium disabled:opacity-60" disabled={busy} onClick={cancel} type="button">
            Cancel
          </button>
        )}
      </div>
      {message && <p className="mt-3 text-sm text-emerald-700" role="status">{message}</p>}
      {error && <p className="mt-3 text-sm text-red-700" role="alert">{error}</p>}
    </form>
  );
}
