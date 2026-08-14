import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { KnownEmailResend } from "./KnownEmailResend";

function response(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as Response;
}

describe("KnownEmailResend", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("resends to the known registration email without rendering an input", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      response({
        detail: "If an eligible unverified account exists and the resend cooldown has elapsed, a verification email will be sent.",
      }, true, 202),
    );
    const user = userEvent.setup();
    render(<KnownEmailResend email="registered@example.com" />);

    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Didn't receive the email? Resend verification" }));

    expect(await screen.findByRole("status")).toHaveTextContent("resend cooldown has elapsed");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/resend-verification/",
      expect.objectContaining({ body: JSON.stringify({ email: "registered@example.com" }) }),
    );
  });

  it("keeps resend success and failure feedback mutually exclusive", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(response({ detail: "Request accepted." }, true, 202))
      .mockRejectedValueOnce(new TypeError("offline"));
    const user = userEvent.setup();
    render(<KnownEmailResend email="registered@example.com" />);
    const resend = screen.getByRole("button", { name: "Didn't receive the email? Resend verification" });

    await user.click(resend);
    expect(await screen.findByRole("status")).toHaveTextContent("Request accepted");
    await user.click(resend);

    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to request");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
