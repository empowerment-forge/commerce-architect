import { loginAccount, logoutAccount } from "./auth";
import { apiGet, apiRequest } from "./client";

function response(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as Response;
}

describe("API client", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("adds a bearer token only when provided", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(response({ ok: true }));

    await apiGet("/api/auth/me/", "token-123");
    await apiGet("/api/products/");

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/auth/me/", {
      method: "GET",
      headers: { Authorization: "Bearer token-123" },
      body: undefined,
      credentials: undefined,
    });
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/products/", {
      method: "GET",
      headers: undefined,
      body: undefined,
      credentials: undefined,
    });
  });

  it("sends JSON and exposes structured API errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      response({ email: ["Already used."] }, false, 400),
    );

    await expect(
      apiRequest("/api/auth/change-email/", {
        method: "POST",
        body: { email: "used@example.com" },
      }),
    ).rejects.toMatchObject({
      status: 400,
      body: { email: ["Already used."] },
    });
  });

  it("includes credentials for login and logout", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(response({ access: "abc" }));

    await loginAccount("alice", "secret");
    await logoutAccount();

    expect(fetchMock.mock.calls[0][1]).toMatchObject({ credentials: "include" });
    expect(fetchMock.mock.calls[1][1]).toMatchObject({ credentials: "include" });
  });
});
