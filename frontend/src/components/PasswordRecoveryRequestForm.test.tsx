import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { PasswordRecoveryRequestForm } from "./PasswordRecoveryRequestForm";

function response(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as Response;
}

describe("PasswordRecoveryRequestForm", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("submits an email and shows the generic response", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(response({
      detail: "If an eligible account exists, password recovery instructions will be sent.",
    }, true, 202));
    const user = userEvent.setup();
    render(<PasswordRecoveryRequestForm onCancel={vi.fn()} />);

    await user.type(screen.getByLabelText("Email"), "alice@example.com");
    await user.click(screen.getByRole("button", { name: "Send recovery email" }));

    expect(await screen.findByRole("status")).toHaveTextContent("If an eligible account exists");
    expect(fetchMock).toHaveBeenCalledWith("/api/auth/password-reset/request/", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ email: "alice@example.com" }),
    }));
  });

  it("shows field feedback and clears it on a corrected submission", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(response({ email: ["Enter a valid email address."] }, false, 400))
      .mockResolvedValueOnce(response({ detail: "Check your email." }, true, 202));
    const user = userEvent.setup();
    render(<PasswordRecoveryRequestForm onCancel={vi.fn()} />);

    await user.type(screen.getByLabelText("Email"), "bad@example.com");
    await user.click(screen.getByRole("button", { name: "Send recovery email" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("valid email");
    await user.clear(screen.getByLabelText("Email"));
    await user.type(screen.getByLabelText("Email"), "good@example.com");
    await user.click(screen.getByRole("button", { name: "Send recovery email" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Check your email");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
