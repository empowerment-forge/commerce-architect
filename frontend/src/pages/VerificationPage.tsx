import { useEffect, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { verifyEmail } from "../api/auth";
import { ResendVerificationForm } from "../components/ResendVerificationForm";

type VerificationState =
  | { status: "pending" }
  | { status: "success"; message: string; email: string }
  | { status: "error"; message: string; canResend: boolean };

export function VerificationPage() {
  const [credentials] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    return { uid: params.get("uid"), token: params.get("token") };
  });
  const [state, setState] = useState<VerificationState>(
    credentials.uid && credentials.token
      ? { status: "pending" }
      : { status: "error", message: "This verification link is incomplete.", canResend: true },
  );
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const { uid, token } = credentials;
    window.history.replaceState({}, "", "/verify-email");

    if (!uid || !token) return;

    verifyEmail(uid, token)
      .then((result) => {
        setState({ status: "success", message: result.detail, email: result.email });
      })
      .catch((error: unknown) => {
        const invalid = error instanceof ApiError && error.status === 400;
        const message = invalid
          ? "This verification link is invalid or expired. Request a new email."
          : "Verification is unavailable right now. Please try again.";
        setState({ status: "error", message, canResend: invalid });
      });
  }, [credentials]);

  return (
    <main className="mx-auto max-w-xl px-4 py-16">
      <section className="rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="text-2xl font-bold">Email verification</h1>
        {state.status === "pending" && <p className="mt-4">Verifying your email…</p>}
        {state.status === "success" && (
          <div className="mt-4 text-emerald-700" role="status">
            <p>{state.message}</p>
            <p className="mt-2 font-medium">{state.email}</p>
          </div>
        )}
        {state.status === "error" && (
          <>
            <p className="mt-4 text-red-700" role="alert">{state.message}</p>
            {state.canResend && <ResendVerificationForm />}
          </>
        )}
        <a className="mt-6 inline-block font-medium text-blue-700 underline" href="/">
          Return to login
        </a>
      </section>
    </main>
  );
}
