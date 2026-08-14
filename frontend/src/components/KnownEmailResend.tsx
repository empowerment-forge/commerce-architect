import { useState } from "react";

import { resendVerification } from "../api/auth";
import { ApiError } from "../api/client";

type KnownEmailResendProps = {
  email: string;
};

export function KnownEmailResend({ email }: KnownEmailResendProps) {
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function resend() {
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      const result = await resendVerification(email);
      setError(null);
      setMessage(result.detail);
    } catch (requestError) {
      setMessage(null);
      const detail = requestError instanceof ApiError && typeof requestError.body.detail === "string"
        ? requestError.body.detail
        : "Unable to request another verification email. Please try again.";
      setError(detail);
    } finally {
      setBusy(false);
    }
  }

  function dismiss() {
    setMessage(null);
    setError(null);
  }

  return (
    <div className="mt-4">
      <button className="text-sm font-medium text-blue-700 underline disabled:opacity-60" disabled={busy} onClick={resend} type="button">
        {busy ? "Requesting…" : "Didn't receive the email? Resend verification"}
      </button>
      {(message || error) && (
        <div className="mt-3">
          {message && <p className="text-sm text-emerald-700" role="status">{message}</p>}
          {error && <p className="text-sm text-red-700" role="alert">{error}</p>}
          <button className="mt-2 text-sm font-medium text-slate-600 underline" onClick={dismiss} type="button">Dismiss</button>
        </div>
      )}
    </div>
  );
}
