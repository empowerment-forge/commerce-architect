import { apiRequest } from "./client";

export type AuthUser = {
  id: number;
  username: string;
  email: string;
  email_verified: boolean;
  email_verified_at: string | null;
};

export type RegistrationResult = {
  id: number;
  username: string;
  email: string;
  email_verified: false;
  detail: string;
};

export type VerificationResult = {
  code: "verified" | "already_verified";
  detail: string;
  email: string;
  email_verified: true;
  verified_at: string;
};

export function registerAccount(username: string, email: string, password: string) {
  return apiRequest<RegistrationResult>("/api/auth/register/", {
    method: "POST",
    body: { username, email, password },
  });
}

export function verifyEmail(uid: string, token: string) {
  return apiRequest<VerificationResult>("/api/auth/verify-email/", {
    method: "POST",
    body: { uid, token },
  });
}

export function resendVerification(email: string) {
  return apiRequest<{ detail: string }>("/api/auth/resend-verification/", {
    method: "POST",
    body: { email },
  });
}

export function resendVerificationAuthenticated(accessToken: string) {
  return apiRequest<{ code: "verification_email_sent"; detail: string }>("/api/auth/resend-verification-authenticated/", {
    method: "POST",
    token: accessToken,
  });
}

export function loginAccount(username: string, password: string) {
  return apiRequest<{ access: string }>("/api/auth/token/", {
    method: "POST",
    body: { username, password },
    credentials: "include",
  });
}

export function refreshAccessToken() {
  return apiRequest<{ access: string }>("/api/auth/refresh/", {
    method: "POST",
    credentials: "include",
  });
}

export function getCurrentUser(accessToken: string) {
  return apiRequest<AuthUser>("/api/auth/me/", { token: accessToken });
}

export function changeEmail(accessToken: string, email: string) {
  return apiRequest<{ email: string; email_verified: false; detail: string }>(
    "/api/auth/change-email/",
    { method: "POST", body: { email }, token: accessToken },
  );
}

export function logoutAccount() {
  return apiRequest<{ detail: string }>("/api/auth/logout/", {
    method: "POST",
    credentials: "include",
  });
}
