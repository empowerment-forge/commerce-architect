import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import App from "./App";

function response(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as Response;
}

const verifiedUser = {
  id: 1,
  username: "alice",
  first_name: "Alice",
  last_name: "Architect",
  phone: "+1 317 555 0123",
  email: "alice@example.com",
  email_verified: true,
  email_verified_at: "2026-08-13T12:00:00Z",
};

function mockApi(routes: Record<string, () => Response>) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const path = String(input);
    return routes[path]?.() ?? response([], true);
  });
}

async function openAndFillRegistration() {
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Login | Register" }));
  await screen.findByRole("heading", { name: "Welcome back" });
  await user.click(screen.getByRole("button", { name: "Show register form" }));
  await user.type(screen.getByLabelText("Username"), "alice");
  await user.type(screen.getByLabelText("First name *"), "Alice");
  await user.type(screen.getByLabelText("Last name *"), "Architect");
  await user.type(screen.getByLabelText("Email"), "alice@example.com");
  await user.type(screen.getByLabelText("Password"), "SecurePass123!");
  return user;
}

describe("App authentication flow", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.history.replaceState({}, "", "/");
  });

  it("attempts one startup refresh and keeps authentication hidden after failure", async () => {
    const fetchMock = mockApi({
      "/api/auth/refresh/": () => response({ detail: "Missing" }, false, 401),
    });

    render(<App />);

    expect(await screen.findByRole("button", { name: "Login | Register" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Welcome back" })).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/auth/refresh/")).toHaveLength(1);
  });

  it("opens the existing Login form only on the explicit login route", async () => {
    window.history.replaceState({}, "", "/login");
    mockApi({ "/api/auth/refresh/": () => response({}, false, 401) });

    render(<App />);

    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
    expect(screen.getByLabelText("Username or Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Show login form" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Show register form" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.queryByLabelText("Email")).not.toBeInTheDocument();
  });

  it("offers password recovery as a secondary login action with back navigation", async () => {
    mockApi({ "/api/auth/refresh/": () => response({}, false, 401) });
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Login | Register" }));
    await user.click(screen.getByRole("button", { name: "Forgot password?" }));
    expect(screen.getByRole("heading", { name: "Reset your password" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Username")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Back to login" }));
    expect(screen.getByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("keeps the two login recovery actions distinct and preserves both flows", async () => {
    mockApi({ "/api/auth/refresh/": () => response({}, false, 401) });
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Login | Register" }));

    const forgot = screen.getByRole("button", { name: "Forgot password?" });
    const resend = screen.getByRole("button", { name: "Need another verification email?" });
    expect(forgot).not.toBe(resend);
    expect(forgot.parentElement).toContainElement(resend);
    expect(forgot.parentElement?.querySelector('[aria-hidden="true"]')).toBeInTheDocument();

    await user.click(resend);
    expect(screen.getByLabelText("Email address")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    await user.click(screen.getByRole("button", { name: "Forgot password?" }));
    expect(screen.getByRole("heading", { name: "Reset your password" })).toBeInTheDocument();
  });

  it("clears authentication feedback when the panel is closed and reopened", async () => {
    mockApi({
      "/api/auth/refresh/": () => response({}, false, 401),
      "/api/auth/token/": () => response({ detail: "No active account found" }, false, 401),
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "Login | Register" }));
    await user.type(screen.getByLabelText("Username or Email"), "alice");
    await user.type(screen.getByLabelText("Password"), "wrong-password");
    await user.click(screen.getByRole("button", { name: "Login" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("No active account found");
    await user.click(screen.getByRole("button", { name: "Close" }));
    await user.click(screen.getByRole("button", { name: "Login | Register" }));

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("registers and shows the check-email result", async () => {
    const fetchMock = mockApi({
      "/api/auth/refresh/": () => response({}, false, 401),
      "/api/auth/register/": () => response({
        id: 1,
        username: "alice",
        email: "alice@example.com",
        email_verified: false,
        detail: "Registration succeeded. Check your email to verify the account.",
      }, true, 201),
      "/api/auth/resend-verification/": () => response({
        detail: "If an eligible unverified account exists and the resend cooldown has elapsed, a verification email will be sent.",
      }, true, 202),
    });
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Login | Register" }));
    await screen.findByRole("heading", { name: "Welcome back" });

    await user.click(screen.getByRole("button", { name: "Show register form" }));
    await user.type(screen.getByLabelText("Username"), "alice");
    await user.type(screen.getByLabelText("First name *"), "Alice");
    await user.type(screen.getByLabelText("Last name *"), "Architect");
    await user.type(screen.getByLabelText("Email"), "alice@example.com");
    await user.type(screen.getByLabelText("Password"), "SecurePass123!");
    await user.click(screen.getByRole("button", { name: "Register" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Check your email");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/register/",
      expect.objectContaining({
        body: JSON.stringify({
          username: "alice",
          first_name: "Alice",
          last_name: "Architect",
          phone: "",
          email: "alice@example.com",
          password: "SecurePass123!",
        }),
      }),
    );
    expect(screen.queryByLabelText("Email address")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Didn't receive the email? Resend verification" }));
    expect(screen.queryByLabelText("Email address")).not.toBeInTheDocument();
    expect(await screen.findByText(/resend cooldown has elapsed/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/resend-verification/",
      expect.objectContaining({ body: JSON.stringify({ email: "alice@example.com" }) }),
    );
  });

  it("offers public resend recovery before registration or login", async () => {
    const fetchMock = mockApi({
      "/api/auth/refresh/": () => response({}, false, 401),
      "/api/auth/resend-verification/": () => response({
        detail: "If an eligible unverified account exists and the resend cooldown has elapsed, a verification email will be sent.",
      }, true, 202),
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "Login | Register" }));
    await user.click(screen.getByRole("button", { name: "Need another verification email?" }));
    await user.type(screen.getByLabelText("Email address"), "recover@example.com");
    await user.click(screen.getByRole("button", { name: "Resend verification email" }));

    expect(await screen.findByRole("status")).toHaveTextContent("eligible unverified account");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/resend-verification/",
      expect.objectContaining({ body: JSON.stringify({ email: "recover@example.com" }) }),
    );
  });

  it("shows a password validation error at the password field", async () => {
    mockApi({
      "/api/auth/refresh/": () => response({}, false, 401),
      "/api/auth/register/": () => response({
        password: ["The password is too similar to the username."],
      }, false, 400),
    });
    render(<App />);
    const user = await openAndFillRegistration();
    await user.click(screen.getByRole("button", { name: "Register" }));

    const password = screen.getByLabelText("Password");
    await waitFor(() => expect(password).toHaveAccessibleDescription("The password is too similar to the username."));
    expect(password).toHaveAttribute("aria-invalid", "true");
  });

  it("shows username and email errors at their corresponding fields", async () => {
    mockApi({
      "/api/auth/refresh/": () => response({}, false, 401),
      "/api/auth/register/": () => response({
        username: ["A user with that username already exists."],
        email: ["A user with that email already exists."],
      }, false, 400),
    });
    render(<App />);
    const user = await openAndFillRegistration();
    await user.click(screen.getByRole("button", { name: "Register" }));

    await waitFor(() => {
      expect(screen.getByLabelText("Username")).toHaveAccessibleDescription("A user with that username already exists.");
      expect(screen.getByLabelText("Email")).toHaveAccessibleDescription("A user with that email already exists.");
    });
  });

  it("shows multiple password validation messages", async () => {
    mockApi({
      "/api/auth/refresh/": () => response({}, false, 401),
      "/api/auth/register/": () => response({
        password: [
          "The password is too similar to the username.",
          "This password is too common.",
        ],
      }, false, 400),
    });
    render(<App />);
    const user = await openAndFillRegistration();
    await user.click(screen.getByRole("button", { name: "Register" }));

    const password = screen.getByLabelText("Password");
    await waitFor(() => {
      expect(password).toHaveAccessibleDescription("The password is too similar to the username. This password is too common.");
    });
  });

  it("uses a generic global registration error for a network failure", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      if (String(input) === "/api/auth/refresh/") return response({}, false, 401);
      throw new TypeError("network unavailable");
    });
    render(<App />);
    const user = await openAndFillRegistration();
    await user.click(screen.getByRole("button", { name: "Register" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Registration failed. Please try again.");
  });

  it("clears failed registration feedback after a corrected successful submission", async () => {
    let attempts = 0;
    mockApi({
      "/api/auth/refresh/": () => response({}, false, 401),
      "/api/auth/register/": () => {
        attempts += 1;
        return attempts === 1
          ? response({}, false, 500)
          : response({
              id: 1,
              username: "alice",
              email: "alice@example.com",
              email_verified: false,
              detail: "Registration succeeded. Check your email to verify the account.",
            }, true, 201);
      },
    });
    render(<App />);
    const user = await openAndFillRegistration();
    await user.click(screen.getByRole("button", { name: "Register" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Registration failed. Please try again.");

    await user.click(screen.getByRole("button", { name: "Register" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Registration succeeded");
    expect(screen.queryByText("Registration failed. Please try again.")).not.toBeInTheDocument();
  });

  it("shows the verified-email enforcement error on login", async () => {
    mockApi({
      "/api/auth/refresh/": () => response({}, false, 401),
      "/api/auth/token/": () => response({ code: "email_not_verified" }, false, 403),
    });
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Login | Register" }));
    await screen.findByRole("heading", { name: "Welcome back" });

    await user.type(screen.getByLabelText("Username or Email"), "alice");
    await user.type(screen.getByLabelText("Password"), "SecurePass123!");
    await user.click(screen.getByRole("button", { name: "Login" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Verify your current email");
    expect(screen.getByLabelText("Email address")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Resend verification email" })).toBeInTheDocument();
  });

  it("shows a useful bad-credentials error", async () => {
    mockApi({
      "/api/auth/refresh/": () => response({}, false, 401),
      "/api/auth/token/": () => response({ detail: "No active account found with the given credentials" }, false, 401),
    });
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Login | Register" }));
    await screen.findByRole("heading", { name: "Welcome back" });

    await user.type(screen.getByLabelText("Username or Email"), "alice");
    await user.type(screen.getByLabelText("Password"), "wrong-password");
    await user.click(screen.getByRole("button", { name: "Login" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("No active account");
  });

  it("logs in, renders /me, changes email, and logs out", async () => {
    const fetchMock = mockApi({
      "/api/auth/refresh/": () => response({}, false, 401),
      "/api/auth/token/": () => response({ access: "access-token" }),
      "/api/auth/me/": () => response(verifiedUser),
      "/api/auth/change-email/": () => response({
        email: "new@example.com",
        email_verified: false,
        detail: "Email changed. Check the new address to verify it.",
      }),
      "/api/auth/logout/": () => response({ detail: "Logged out." }),
    });
    const storageSet = vi.spyOn(Storage.prototype, "setItem");
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Login | Register" }));
    await screen.findByRole("heading", { name: "Welcome back" });

    await user.type(screen.getByLabelText("Username or Email"), "alice");
    await user.type(screen.getByLabelText("Password"), "SecurePass123!");
    await user.click(screen.getByRole("button", { name: "Login" }));
    expect(await screen.findByRole("button", { name: "alice" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Welcome back" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Logout" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "alice" }));
    expect(await screen.findByRole("heading", { name: "Account" })).toBeInTheDocument();
    expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    expect(screen.getByText("Verified")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Resend verification email" })).not.toBeInTheDocument();
    expect(screen.getByText("Account status:")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Update account" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("New email")).not.toBeInTheDocument();
    const accountActions = screen.getByRole("group", { name: "Account actions" });
    expect(accountActions).toHaveClass("flex", "flex-wrap", "gap-3");
    expect(within(accountActions).getByRole("button", { name: "Update account" })).toBeInTheDocument();
    expect(within(accountActions).getByRole("button", { name: "Logout" })).toBeInTheDocument();
    expect(within(accountActions).getByRole("button", { name: "Close" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Update account" }));
    expect(screen.getByRole("heading", { name: "Update account" })).toBeInTheDocument();
    expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    await user.type(screen.getByLabelText("New email"), "new@example.com");
    await user.click(screen.getByRole("button", { name: "Send verification to new email" }));
    expect(await screen.findByText("new@example.com")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Email changed");
    await user.click(screen.getByRole("button", { name: "Back to account" }));
    expect(screen.getByText("Not Verified")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Logout" }));
    expect(await screen.findByRole("button", { name: "Login | Register" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Account" })).not.toBeInTheDocument();
    expect(storageSet).not.toHaveBeenCalled();
    expect(fetchMock.mock.calls.find(([url]) => url === "/api/auth/change-email/" )?.[1]).toMatchObject({
      headers: expect.objectContaining({ Authorization: "Bearer access-token" }),
    });
  });

  it("closes the responsive Account action group without changing the session", async () => {
    mockApi({
      "/api/auth/refresh/": () => response({ access: "restored-token" }),
      "/api/auth/me/": () => response(verifiedUser),
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "alice" }));
    const accountActions = screen.getByRole("group", { name: "Account actions" });
    await user.click(within(accountActions).getByRole("button", { name: "Close" }));

    expect(screen.queryByRole("heading", { name: "Account" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "alice" })).toBeInTheDocument();
  });

  it("keeps Update Account actions responsive and returns to the Account panel", async () => {
    mockApi({
      "/api/auth/refresh/": () => response({ access: "restored-token" }),
      "/api/auth/me/": () => response(verifiedUser),
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "alice" }));
    await user.click(screen.getByRole("button", { name: "Update account" }));

    expect(screen.getByRole("heading", { name: "Update account" })).toBeInTheDocument();
    const updateActions = screen.getByRole("group", { name: "Update account actions" });
    expect(updateActions).toHaveClass("flex", "flex-wrap", "gap-3");
    expect(updateActions.parentElement).toHaveClass("flex", "flex-wrap", "gap-4");
    const backButton = within(updateActions).getByRole("button", { name: "Back to account" });
    expect(backButton).toBeEnabled();

    expect(screen.getByRole("button", { name: "Send verification to new email" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Change email" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cancel" })).not.toBeInTheDocument();

    await user.click(backButton);
    expect(screen.getByRole("heading", { name: "Account" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Update account" })).not.toBeInTheDocument();
  });

  it("restores /me from one refresh-cookie request", async () => {
    const fetchMock = mockApi({
      "/api/auth/refresh/": () => response({ access: "restored-token" }),
      "/api/auth/me/": () => response(verifiedUser),
    });

    render(<App />);

    expect(await screen.findByRole("button", { name: "alice" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Welcome back" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Account" })).not.toBeInTheDocument();
    await waitFor(() => {
      expect(fetchMock.mock.calls.filter(([url]) => url === "/api/auth/refresh/")).toHaveLength(1);
    });
  });

  it("silently refreshes stale access for change-email and stays logged in", async () => {
    let refreshCalls = 0;
    let changeCalls = 0;
    const fetchMock = mockApi({
      "/api/auth/refresh/": () => {
        refreshCalls += 1;
        return response({ access: refreshCalls === 1 ? "stale-access" : "fresh-access" });
      },
      "/api/auth/me/": () => response(verifiedUser),
      "/api/auth/change-email/": () => {
        changeCalls += 1;
        return changeCalls === 1
          ? response({ detail: "Given token not valid for any token type", code: "token_not_valid" }, false, 401)
          : response({ email: "new@example.com", email_verified: false, detail: "Email changed" });
      },
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "alice" }));
    await user.click(screen.getByRole("button", { name: "Update account" }));
    await user.type(screen.getByLabelText("New email"), "new@example.com");
    await user.click(screen.getByRole("button", { name: "Send verification to new email" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Email changed");
    expect(screen.getByRole("button", { name: "alice" })).toBeInTheDocument();
    expect(refreshCalls).toBe(2);
    expect(changeCalls).toBe(2);
    const changeRequests = fetchMock.mock.calls.filter(([url]) => url === "/api/auth/change-email/");
    expect(changeRequests[1][1]).toMatchObject({
      headers: expect.objectContaining({ Authorization: "Bearer fresh-access" }),
    });
  });

  it("returns to login with a safe message when stale access cannot refresh", async () => {
    let refreshCalls = 0;
    mockApi({
      "/api/auth/refresh/": () => {
        refreshCalls += 1;
        return refreshCalls === 1
          ? response({ access: "stale-access" })
          : response({ detail: "Token is blacklisted", code: "token_not_valid" }, false, 401);
      },
      "/api/auth/me/": () => response(verifiedUser),
      "/api/auth/change-email/": () => response(
        { detail: "Given token not valid for any token type", code: "token_not_valid" },
        false,
        401,
      ),
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "alice" }));
    await user.click(screen.getByRole("button", { name: "Update account" }));
    await user.type(screen.getByLabelText("New email"), "new@example.com");
    await user.click(screen.getByRole("button", { name: "Send verification to new email" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Your session has expired. Please log in again.");
    expect(screen.queryByText(/Given token not valid/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Login | Register" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "alice" })).not.toBeInTheDocument();
  });

  it("offers authenticated resend only for an unverified account and uses its access token", async () => {
    const fetchMock = mockApi({
      "/api/auth/refresh/": () => response({ access: "restored-token" }),
      "/api/auth/me/": () => response({
        ...verifiedUser,
        email: "current@example.com",
        email_verified: false,
        email_verified_at: null,
      }),
      "/api/auth/resend-verification-authenticated/": () => response({
        code: "verification_email_sent",
        detail: "Verification email sent to your current email address.",
      }, true, 202),
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "alice" }));
    expect(await screen.findByText("Not Verified")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Resend verification email" }));

    expect(await screen.findByRole("status")).toHaveTextContent("current email address");
    const resendCall = fetchMock.mock.calls.find(
      ([url]) => url === "/api/auth/resend-verification-authenticated/",
    );
    expect(resendCall?.[1]).toMatchObject({
      method: "POST",
      headers: expect.objectContaining({ Authorization: "Bearer restored-token" }),
    });
    expect(resendCall?.[1]).toHaveProperty("body", undefined);
  });

  it("shows explicit authenticated resend cooldown feedback without stale success", async () => {
    let attempts = 0;
    mockApi({
      "/api/auth/refresh/": () => response({ access: "restored-token" }),
      "/api/auth/me/": () => response({
        ...verifiedUser,
        email_verified: false,
        email_verified_at: null,
      }),
      "/api/auth/resend-verification-authenticated/": () => {
        attempts += 1;
        return attempts === 1
          ? response({ code: "verification_email_sent", detail: "Verification email sent to your current email address." }, true, 202)
          : response({ code: "resend_cooldown", detail: "A verification email was sent recently. Try again in 60 seconds.", retry_after_seconds: 60 }, false, 429);
      },
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "alice" }));
    await user.click(screen.getByRole("button", { name: "Resend verification email" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Verification email sent");
    await user.click(screen.getByRole("button", { name: "Resend verification email" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Try again in 60 seconds");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("shows the committed unverified address when email-change delivery fails", async () => {
    mockApi({
      "/api/auth/refresh/": () => response({ access: "restored-token" }),
      "/api/auth/me/": () => response(verifiedUser),
      "/api/auth/change-email/": () => response({
        code: "verification_delivery_failed",
        detail: "The account is unverified and the email could not be sent. Try resending.",
        email: "new@example.com",
        email_verified: false,
      }, false, 503),
    });
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "alice" }));
    expect(await screen.findByText("alice@example.com")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Update account" }));
    await user.type(screen.getByLabelText("New email"), "new@example.com");
    await user.click(screen.getByRole("button", { name: "Send verification to new email" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("could not be sent");
    expect(screen.getByText("new@example.com")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Back to account" }));
    expect(screen.getByText("Not Verified")).toBeInTheDocument();
  });

  it("clears a failed email-change error after a corrected successful change", async () => {
    let attempts = 0;
    mockApi({
      "/api/auth/refresh/": () => response({ access: "restored-token" }),
      "/api/auth/me/": () => response(verifiedUser),
      "/api/auth/change-email/": () => {
        attempts += 1;
        return attempts === 1
          ? response({ email: ["A user with that email already exists."] }, false, 400)
          : response({
              email: "corrected@example.com",
              email_verified: false,
              detail: "Email changed. Check the new address to verify it.",
            });
      },
    });
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "alice" }));
    expect(await screen.findByText("alice@example.com")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Update account" }));

    await user.type(screen.getByLabelText("New email"), "taken@example.com");
    await user.click(screen.getByRole("button", { name: "Send verification to new email" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("already exists");

    await user.clear(screen.getByLabelText("New email"));
    await user.type(screen.getByLabelText("New email"), "corrected@example.com");
    await user.click(screen.getByRole("button", { name: "Send verification to new email" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Email changed");
    expect(screen.queryByText("A user with that email already exists.")).not.toBeInTheDocument();
    expect(screen.getByText("corrected@example.com")).toBeInTheDocument();
  });

  it("shows complete identity and all three independent update forms immediately", async () => {
    mockApi({
      "/api/auth/refresh/": () => response({ access: "restored-token" }),
      "/api/auth/me/": () => response(verifiedUser),
    });
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "alice" }));
    const identity = screen.getByRole("heading", { name: "Account" }).parentElement;
    expect(identity).toHaveTextContent("Username: alice");
    expect(identity).toHaveTextContent("Name: Alice Architect");
    expect(identity).toHaveTextContent("Phone: +1 317 555 0123");
    expect(identity).toHaveTextContent("Email: alice@example.com");

    await user.click(screen.getByRole("button", { name: "Update account" }));
    expect(screen.getByRole("heading", { name: "Personal information" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Email" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Password" })).toBeInTheDocument();
    expect(screen.getByLabelText("First name")).toHaveValue("Alice");
    expect(screen.getByLabelText("Last name")).toHaveValue("Architect");
    expect(screen.getByLabelText(/Phone/)).toHaveValue("+1 317 555 0123");
    expect(screen.getByText("(required for SMS messages)")).toBeInTheDocument();
    for (const label of ["Current password", "New password", "Confirm new password"]) {
      const input = screen.getByLabelText(label);
      expect(input).toHaveAttribute("type", "password");
      expect(input).toHaveValue("");
    }
    expect(screen.queryByRole("button", { name: "Change email" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cancel" })).not.toBeInTheDocument();
  });

  it("updates personal information independently and reflects it in Account", async () => {
    const fetchMock = mockApi({
      "/api/auth/refresh/": () => response({ access: "restored-token" }),
      "/api/auth/me/": () => response(verifiedUser),
    });
    fetchMock.mockImplementation(async (input, options) => {
      if (String(input) === "/api/auth/refresh/") return response({ access: "restored-token" });
      if (String(input) === "/api/auth/me/" && options?.method === "PATCH") {
        return response({
          first_name: "Alicia",
          last_name: "Builder",
          phone: "+1 317 555 0199",
          detail: "Personal information updated.",
        });
      }
      if (String(input) === "/api/auth/me/") return response(verifiedUser);
      return response([]);
    });
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "alice" }));
    await user.click(screen.getByRole("button", { name: "Update account" }));

    await user.clear(screen.getByLabelText("First name"));
    await user.type(screen.getByLabelText("First name"), "Alicia");
    await user.clear(screen.getByLabelText("Last name"));
    await user.type(screen.getByLabelText("Last name"), "Builder");
    await user.clear(screen.getByLabelText(/Phone/));
    await user.type(screen.getByLabelText(/Phone/), "+1 317 555 0199");
    await user.click(screen.getByRole("button", { name: "Update information" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Personal information updated");
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/auth/change-email/")).toHaveLength(0);
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/auth/password-change/")).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: "Back to account" }));
    expect(screen.getByText("Alicia Builder")).toBeInTheDocument();
    expect(screen.getByText("+1 317 555 0199")).toBeInTheDocument();
  });

  it("keeps password failures authenticated and logs out with success feedback after change", async () => {
    let attempts = 0;
    mockApi({
      "/api/auth/refresh/": () => response({ access: "restored-token" }),
      "/api/auth/me/": () => response(verifiedUser),
      "/api/auth/password-change/": () => {
        attempts += 1;
        return attempts === 1
          ? response({ current_password: ["Current password is incorrect."] }, false, 400)
          : response({
              code: "password_changed",
              detail: "Password changed successfully. Please sign in again.",
            });
      },
    });
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "alice" }));
    await user.click(screen.getByRole("button", { name: "Update account" }));

    await user.type(screen.getByLabelText("Current password"), "wrong-password");
    await user.type(screen.getByLabelText("New password"), "OtherSecure456!");
    await user.type(screen.getByLabelText("Confirm new password"), "OtherSecure456!");
    await user.click(screen.getByRole("button", { name: "Change password" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Current password is incorrect");
    expect(screen.getByRole("button", { name: "alice" })).toBeInTheDocument();

    await user.clear(screen.getByLabelText("Current password"));
    await user.type(screen.getByLabelText("Current password"), "SecurePass123!");
    await user.click(screen.getByRole("button", { name: "Change password" }));
    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Password changed successfully");
    expect(screen.queryByRole("button", { name: "alice" })).not.toBeInTheDocument();
  });

  it("renders legacy blank identity values without undefined or spacing artifacts", async () => {
    mockApi({
      "/api/auth/refresh/": () => response({ access: "restored-token" }),
      "/api/auth/me/": () => response({
        ...verifiedUser,
        first_name: "Legacy",
        last_name: "",
        phone: "",
      }),
    });
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "alice" }));
    expect(screen.getByText("Legacy")).toBeInTheDocument();
    expect(screen.getByText("Not set")).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("undefined");
  });
});
