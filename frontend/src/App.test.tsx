import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import App from "./App";

function response(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as Response;
}

const verifiedUser = {
  id: 1,
  username: "alice",
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
  await screen.findByRole("heading", { name: "Welcome back" });
  await user.click(screen.getByRole("button", { name: "Show register form" }));
  await user.type(screen.getByLabelText("Username"), "alice");
  await user.type(screen.getByLabelText("Email"), "alice@example.com");
  await user.type(screen.getByLabelText("Password"), "SecurePass123!");
  return user;
}

describe("App authentication flow", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.history.replaceState({}, "", "/");
  });

  it("attempts one startup refresh and shows login after failure", async () => {
    const fetchMock = mockApi({
      "/api/auth/refresh/": () => response({ detail: "Missing" }, false, 401),
    });

    render(<App />);

    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/auth/refresh/")).toHaveLength(1);
  });

  it("registers and shows the check-email result", async () => {
    mockApi({
      "/api/auth/refresh/": () => response({}, false, 401),
      "/api/auth/register/": () => response({
        id: 1,
        username: "alice",
        email: "alice@example.com",
        email_verified: false,
        detail: "Registration succeeded. Check your email to verify the account.",
      }, true, 201),
    });
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole("heading", { name: "Welcome back" });

    await user.click(screen.getByRole("button", { name: "Show register form" }));
    await user.type(screen.getByLabelText("Username"), "alice");
    await user.type(screen.getByLabelText("Email"), "alice@example.com");
    await user.type(screen.getByLabelText("Password"), "SecurePass123!");
    await user.click(screen.getByRole("button", { name: "Register" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Check your email");
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
    await screen.findByRole("heading", { name: "Welcome back" });

    await user.type(screen.getByLabelText("Username"), "alice");
    await user.type(screen.getByLabelText("Password"), "SecurePass123!");
    await user.click(screen.getByRole("button", { name: "Login" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Verify your current email");
  });

  it("shows a useful bad-credentials error", async () => {
    mockApi({
      "/api/auth/refresh/": () => response({}, false, 401),
      "/api/auth/token/": () => response({ detail: "No active account found with the given credentials" }, false, 401),
    });
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole("heading", { name: "Welcome back" });

    await user.type(screen.getByLabelText("Username"), "alice");
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
    await screen.findByRole("heading", { name: "Welcome back" });

    await user.type(screen.getByLabelText("Username"), "alice");
    await user.type(screen.getByLabelText("Password"), "SecurePass123!");
    await user.click(screen.getByRole("button", { name: "Login" }));
    expect(await screen.findByText("alice@example.com")).toBeInTheDocument();
    expect(screen.getByText("Verified")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Change email"), "new@example.com");
    await user.click(screen.getByRole("button", { name: "Send verification to new email" }));
    expect(await screen.findByText("new@example.com")).toBeInTheDocument();
    expect(screen.getByText("Not verified")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Logout" }));
    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
    expect(storageSet).not.toHaveBeenCalled();
    expect(fetchMock.mock.calls.find(([url]) => url === "/api/auth/change-email/" )?.[1]).toMatchObject({
      headers: expect.objectContaining({ Authorization: "Bearer access-token" }),
    });
  });

  it("restores /me from one refresh-cookie request", async () => {
    const fetchMock = mockApi({
      "/api/auth/refresh/": () => response({ access: "restored-token" }),
      "/api/auth/me/": () => response(verifiedUser),
    });

    render(<App />);

    expect(await screen.findByText("alice@example.com")).toBeInTheDocument();
    await waitFor(() => {
      expect(fetchMock.mock.calls.filter(([url]) => url === "/api/auth/refresh/")).toHaveLength(1);
    });
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
    expect(await screen.findByText("alice@example.com")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Change email"), "new@example.com");
    await user.click(screen.getByRole("button", { name: "Send verification to new email" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("could not be sent");
    expect(screen.getByText("new@example.com")).toBeInTheDocument();
    expect(screen.getByText("Not verified")).toBeInTheDocument();
  });
});
