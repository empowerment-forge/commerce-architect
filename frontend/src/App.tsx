import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";

import {
  changeEmail,
  getCurrentUser,
  loginAccount,
  logoutAccount,
  refreshAccessToken,
  registerAccount,
} from "./api/auth";
import type { AuthUser } from "./api/auth";
import { ApiError } from "./api/client";
import { ResendVerificationForm } from "./components/ResendVerificationForm";
import { ProductListPage } from "./pages/ProductListPage";
import { VerificationPage } from "./pages/VerificationPage";

function errorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof ApiError)) return fallback;
  if (error.body.code === "email_not_verified") {
    return "Verify your current email address before logging in.";
  }
  if (error.body.detail) return error.body.detail;
  const fieldError = Object.values(error.body).find(Array.isArray);
  return Array.isArray(fieldError) && typeof fieldError[0] === "string"
    ? fieldError[0]
    : fallback;
}

type AuthPanelProps = {
  onLogin: (access: string, user: AuthUser) => void;
};

type RegistrationField = "username" | "email" | "password";
type RegistrationFieldErrors = Partial<Record<RegistrationField, string[]>>;

const registrationFields: RegistrationField[] = ["username", "email", "password"];

function registrationErrors(error: ApiError): RegistrationFieldErrors {
  return Object.fromEntries(
    registrationFields.flatMap((field) => {
      const value = error.body[field];
      const messages = Array.isArray(value)
        ? value.filter((item): item is string => typeof item === "string")
        : [];
      return messages.length ? [[field, messages]] : [];
    }),
  );
}

function registrationGlobalError(error: ApiError): string {
  if (typeof error.body.detail === "string") return error.body.detail;
  const nonFieldErrors = error.body.non_field_errors;
  if (Array.isArray(nonFieldErrors)) {
    const messages = nonFieldErrors.filter((item): item is string => typeof item === "string");
    if (messages.length) return messages.join(" ");
  }
  return "Registration failed. Please try again.";
}

function FieldErrors({ field, errors }: { field: RegistrationField; errors?: string[] }) {
  if (!errors?.length) return null;
  return (
    <ul className="mt-1 list-disc pl-5 text-sm font-normal text-red-700" id={`${field}-errors`} role="alert">
      {errors.map((message, index) => <li key={`${field}-${index}`}>{message}</li>)}
    </ul>
  );
}

function AuthPanel({ onLogin }: AuthPanelProps) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<RegistrationFieldErrors>({});
  const [resendEmail, setResendEmail] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    setBusy(true);
    setError(null);
    setMessage(null);
    setFieldErrors({});
    setResendEmail(null);
    const data = new FormData(form);
    try {
      if (mode === "register") {
        const result = await registerAccount(
          String(data.get("username")),
          String(data.get("email")),
          String(data.get("password")),
        );
        setError(null);
        setFieldErrors({});
        setMessage(result.detail);
        setResendEmail(result.email);
        form.reset();
      } else {
        const result = await loginAccount(
          String(data.get("username")),
          String(data.get("password")),
        );
        const user = await getCurrentUser(result.access);
        onLogin(result.access, user);
      }
    } catch (requestError) {
      setMessage(null);
      if (mode === "register" && requestError instanceof ApiError) {
        const nextFieldErrors = registrationErrors(requestError);
        setFieldErrors(nextFieldErrors);
        const hasFieldErrors = Object.keys(nextFieldErrors).length > 0;
        setError(hasFieldErrors ? null : registrationGlobalError(requestError));
      } else {
        if (
          mode === "login"
          && requestError instanceof ApiError
          && requestError.body.code === "email_not_verified"
        ) {
          setResendEmail("");
        }
        setError(errorMessage(requestError, `${mode === "login" ? "Login" : "Registration"} failed. Please try again.`));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex gap-2" aria-label="Authentication mode">
        {(["login", "register"] as const).map((item) => (
          <button
            aria-label={`Show ${item} form`}
            className={`rounded-md px-4 py-2 text-sm font-medium ${mode === item ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-700"}`}
            key={item}
            onClick={() => { setMode(item); setError(null); setMessage(null); setFieldErrors({}); setResendEmail(null); }}
            type="button"
          >
            {item === "login" ? "Login" : "Register"}
          </button>
        ))}
      </div>
      <h2 className="mt-5 text-xl font-semibold">{mode === "login" ? "Welcome back" : "Create account"}</h2>
      <form className="mt-4 space-y-4" onSubmit={submit}>
        <div>
          <label className="block text-sm font-medium" htmlFor="auth-username">Username</label>
          <input aria-describedby={fieldErrors.username ? "username-errors" : undefined} aria-invalid={Boolean(fieldErrors.username)} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" id="auth-username" name="username" required />
          {mode === "register" && <FieldErrors errors={fieldErrors.username} field="username" />}
        </div>
        {mode === "register" && (
          <div>
            <label className="block text-sm font-medium" htmlFor="auth-email">Email</label>
            <input aria-describedby={fieldErrors.email ? "email-errors" : undefined} aria-invalid={Boolean(fieldErrors.email)} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" id="auth-email" name="email" required type="email" />
            <FieldErrors errors={fieldErrors.email} field="email" />
          </div>
        )}
        <div>
          <label className="block text-sm font-medium" htmlFor="auth-password">Password</label>
          <input aria-describedby={fieldErrors.password ? "password-errors" : undefined} aria-invalid={Boolean(fieldErrors.password)} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" id="auth-password" name="password" required type="password" />
          {mode === "register" && <FieldErrors errors={fieldErrors.password} field="password" />}
        </div>
        <button className="rounded-md bg-blue-700 px-4 py-2 font-medium text-white disabled:opacity-60" disabled={busy} type="submit">
          {busy ? "Working…" : mode === "login" ? "Login" : "Register"}
        </button>
      </form>
      {message && <p className="mt-4 text-sm text-emerald-700" role="status">{message}</p>}
      {error && <p className="mt-4 text-sm text-red-700" role="alert">{error}</p>}
      {resendEmail !== null && <ResendVerificationForm collapsed initialEmail={resendEmail} />}
    </section>
  );
}

type AccountPanelProps = {
  accessToken: string;
  user: AuthUser;
  onUserChange: (user: AuthUser) => void;
  onLogout: () => void;
};

function AccountPanel({ accessToken, user, onUserChange, onLogout }: AccountPanelProps) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [changeEmailOpen, setChangeEmailOpen] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [emailBusy, setEmailBusy] = useState(false);

  function clearFeedback() {
    setMessage(null);
    setError(null);
  }

  function closeSettings() {
    clearFeedback();
    setChangeEmailOpen(false);
    setSettingsOpen(false);
  }

  async function submitEmail(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    setEmailBusy(true);
    clearFeedback();
    const email = String(new FormData(form).get("email"));
    try {
      const result = await changeEmail(accessToken, email);
      onUserChange({ ...user, email: result.email, email_verified: false, email_verified_at: null });
      setError(null);
      setMessage(result.detail);
      setChangeEmailOpen(false);
      form.reset();
    } catch (requestError) {
      setMessage(null);
      if (
        requestError instanceof ApiError
        && requestError.body.code === "verification_delivery_failed"
        && typeof requestError.body.email === "string"
      ) {
        onUserChange({
          ...user,
          email: requestError.body.email,
          email_verified: false,
          email_verified_at: null,
        });
      }
      setError(errorMessage(requestError, "Unable to change email. Please try again."));
    } finally {
      setEmailBusy(false);
    }
  }

  if (settingsOpen) {
    return (
      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold">Account settings</h2>
            <p className="mt-2"><span className="font-medium">Current email:</span> {user.email}</p>
          </div>
          <button className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium disabled:opacity-60" disabled={emailBusy} onClick={closeSettings} type="button">Back to account</button>
        </div>
        {!changeEmailOpen ? (
          <button
            className="mt-6 rounded-md bg-blue-700 px-4 py-2 font-medium text-white"
            onClick={() => { clearFeedback(); setChangeEmailOpen(true); }}
            type="button"
          >
            Change email
          </button>
        ) : (
          <form className="mt-6 border-t border-slate-200 pt-5" onSubmit={submitEmail}>
            <label className="block text-sm font-medium">
              New email
              <input className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" name="email" required type="email" />
            </label>
            <div className="mt-3 flex gap-3">
              <button className="rounded-md bg-blue-700 px-4 py-2 font-medium text-white disabled:opacity-60" disabled={emailBusy} type="submit">{emailBusy ? "Changing…" : "Send verification to new email"}</button>
              <button className="rounded-md border border-slate-300 px-4 py-2 font-medium disabled:opacity-60" disabled={emailBusy} onClick={() => { clearFeedback(); setChangeEmailOpen(false); }} type="button">Cancel</button>
            </div>
          </form>
        )}
        {message && <p className="mt-4 text-sm text-emerald-700" role="status">{message}</p>}
        {error && <p className="mt-4 text-sm text-red-700" role="alert">{error}</p>}
      </section>
    );
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold">Authenticated account</h2>
          <p className="mt-2"><span className="font-medium">Username:</span> {user.username}</p>
          <p><span className="font-medium">Email:</span> {user.email}</p>
          <p>
            <span className="font-medium">Verification:</span>{" "}
            {user.email_verified ? "Verified" : "Not verified"}
          </p>
        </div>
        <div className="flex gap-3">
          <button className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium" onClick={() => { clearFeedback(); setSettingsOpen(true); }} type="button">Account settings</button>
          <button className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium" onClick={onLogout} type="button">Logout</button>
        </div>
      </div>
    </section>
  );
}

function App() {
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [restoring, setRestoring] = useState(true);
  const refreshStarted = useRef(false);

  useEffect(() => {
    if (refreshStarted.current) return;
    refreshStarted.current = true;
    refreshAccessToken()
      .then(async ({ access }) => {
        const currentUser = await getCurrentUser(access);
        setAccessToken(access);
        setUser(currentUser);
      })
      .catch(() => {
        setAccessToken(null);
        setUser(null);
      })
      .finally(() => setRestoring(false));
  }, []);

  if (window.location.pathname === "/verify-email") return <VerificationPage />;

  async function logout() {
    try {
      await logoutAccount();
    } catch {
      // Local authentication state must clear even if server cleanup is unavailable.
    } finally {
      setAccessToken(null);
      setUser(null);
    }
  }

  return (
    <>
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-6xl px-4 py-5 sm:px-6">
          <h1 className="text-2xl font-bold">Commerce Architect</h1>
          <p className="mt-1 text-sm text-slate-600">Authentication and catalog development surface</p>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 pt-8 sm:px-6">
        {restoring ? (
          <p className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">Restoring session…</p>
        ) : user && accessToken ? (
          <AccountPanel accessToken={accessToken} onLogout={logout} onUserChange={setUser} user={user} />
        ) : (
          <AuthPanel onLogin={(access, currentUser) => { setAccessToken(access); setUser(currentUser); }} />
        )}
      </main>
      <ProductListPage />
    </>
  );
}

export default App;
