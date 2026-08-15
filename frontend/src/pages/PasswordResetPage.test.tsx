import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { PasswordResetPage } from "./PasswordResetPage";

function response(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as Response;
}

describe("PasswordResetPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.history.replaceState({}, "", "/reset-password?uid=reset-id&token=secret-token");
  });

  it("captures credentials and immediately removes them from the URL", async () => {
    render(<PasswordResetPage onReset={vi.fn()} />);
    await waitFor(() => expect(window.location.href).not.toContain("secret-token"));
    expect(window.location.pathname).toBe("/reset-password");
    expect(window.location.search).toBe("");
  });

  it("rejects mismatch before submission", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");
    const user = userEvent.setup();
    render(<PasswordResetPage onReset={vi.fn()} />);
    await user.type(screen.getByLabelText("New password"), "NewSecure123!");
    await user.type(screen.getByLabelText("Confirm password"), "different");
    await user.click(screen.getByRole("button", { name: "Change password" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Passwords do not match");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows backend password feedback without exposing the token", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(response({
      new_password: ["This password is too common."],
    }, false, 400));
    const user = userEvent.setup();
    render(<PasswordResetPage onReset={vi.fn()} />);
    await user.type(screen.getByLabelText("New password"), "password");
    await user.type(screen.getByLabelText("Confirm password"), "password");
    await user.click(screen.getByRole("button", { name: "Change password" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("too common");
    expect(document.body).not.toHaveTextContent("secret-token");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("handles invalid links safely", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(response({
      code: "invalid_or_expired_token",
      detail: "This password reset link is invalid or expired.",
    }, false, 400));
    const user = userEvent.setup();
    render(<PasswordResetPage onReset={vi.fn()} />);
    await user.type(screen.getByLabelText("New password"), "NewSecure123!");
    await user.type(screen.getByLabelText("Confirm password"), "NewSecure123!");
    await user.click(screen.getByRole("button", { name: "Change password" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("invalid or expired");
  });

  it("clears session state and returns to login after success", async () => {
    const onReset = vi.fn();
    const storageSet = vi.spyOn(Storage.prototype, "setItem");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(response({
      code: "password_reset",
      detail: "Password changed. Please log in.",
    }));
    const user = userEvent.setup();
    render(<PasswordResetPage onReset={onReset} />);
    await user.type(screen.getByLabelText("New password"), "NewSecure123!");
    await user.type(screen.getByLabelText("Confirm password"), "NewSecure123!");
    await user.click(screen.getByRole("button", { name: "Change password" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Please log in");
    expect(screen.getByRole("link", { name: "Return to login" })).toHaveAttribute("href", "/login");
    expect(onReset).toHaveBeenCalledTimes(1);
    expect(storageSet).not.toHaveBeenCalled();
    expect(fetchMock).toHaveBeenCalledWith("/api/auth/password-reset/confirm/", expect.objectContaining({
      credentials: "include",
      body: expect.stringContaining('"token":"secret-token"'),
    }));
    expect(screen.queryByLabelText("New password")).not.toBeInTheDocument();
  });
});
