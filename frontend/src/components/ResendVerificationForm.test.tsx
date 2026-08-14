import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ResendVerificationForm } from "./ResendVerificationForm";

function response(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as Response;
}

describe("ResendVerificationForm", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("submits the email and displays the enumeration-resistant response", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      response({
        detail: "If an eligible unverified account exists, a verification email will be sent.",
      }, true, 202),
    );
    const user = userEvent.setup();
    render(<ResendVerificationForm initialEmail="alice@example.com" />);

    await user.click(screen.getByRole("button", { name: "Resend verification email" }));

    expect(await screen.findByRole("status")).toHaveTextContent("If an eligible unverified account exists");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/resend-verification/",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ email: "alice@example.com" }),
      }),
    );
  });

  it("shows a safe fallback when the resend request is unavailable", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("offline"));
    const user = userEvent.setup();
    render(<ResendVerificationForm />);

    await user.type(screen.getByLabelText("Email address"), "alice@example.com");
    await user.click(screen.getByRole("button", { name: "Resend verification email" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to request another verification email");
  });

  it("keeps the full form collapsed until recovery is requested", async () => {
    const user = userEvent.setup();
    render(<ResendVerificationForm collapsed initialEmail="alice@example.com" />);

    expect(screen.queryByLabelText("Email address")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Didn't receive the email? Resend verification" }));

    expect(screen.getByLabelText("Email address")).toHaveValue("alice@example.com");
  });

  it("cancels an expanded recovery form and clears transient feedback", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      response({ detail: "If an eligible unverified account exists, a verification email will be sent." }, true, 202),
    );
    const user = userEvent.setup();
    render(<ResendVerificationForm collapsed initialEmail="alice@example.com" />);

    await user.click(screen.getByRole("button", { name: "Didn't receive the email? Resend verification" }));
    await user.click(screen.getByRole("button", { name: "Resend verification email" }));
    expect(await screen.findByRole("status")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.queryByLabelText("Email address")).not.toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
