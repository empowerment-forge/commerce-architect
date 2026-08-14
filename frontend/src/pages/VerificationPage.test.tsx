import { render, screen } from "@testing-library/react";

import { VerificationPage } from "./VerificationPage";

function response(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as Response;
}

describe("VerificationPage", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("verifies query credentials once and removes them from browser history", async () => {
    window.history.replaceState({}, "", "/verify-email?uid=user-id&token=raw-secret");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      response({
        code: "verified",
        detail: "Email address verified.",
        email: "alice@example.com",
        email_verified: true,
        verified_at: "2026-08-13T12:00:00Z",
      }),
    );

    render(<VerificationPage />);

    expect(await screen.findByText("Email address verified.")).toBeInTheDocument();
    expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    expect(window.location.search).toBe("");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("shows an actionable invalid-link error", async () => {
    window.history.replaceState({}, "", "/verify-email?uid=user-id&token=bad");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      response({ code: "invalid_or_expired_token" }, false, 400),
    );

    render(<VerificationPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent("invalid or expired");
  });

  it("shows an already-verified result as success", async () => {
    window.history.replaceState({}, "", "/verify-email?uid=user-id&token=used");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      response({
        code: "already_verified",
        detail: "This email address is already verified.",
        email: "alice@example.com",
        email_verified: true,
        verified_at: "2026-08-13T12:00:00Z",
      }),
    );

    render(<VerificationPage />);

    expect(await screen.findByRole("status")).toHaveTextContent("already verified");
  });

  it("shows a retryable network error", async () => {
    window.history.replaceState({}, "", "/verify-email?uid=user-id&token=secret");
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("offline"));

    render(<VerificationPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent("unavailable");
  });

  it("rejects an incomplete link without making a request", async () => {
    window.history.replaceState({}, "", "/verify-email");
    const fetchMock = vi.spyOn(globalThis, "fetch");

    render(<VerificationPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent("incomplete");
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
