import { loginAccount, logoutAccount, refreshAccessToken } from "./auth";
import {
  apiGet,
  apiRequest,
  createAuthenticatedRequester,
  SessionExpiredError,
  SESSION_EXPIRED_MESSAGE,
} from "./client";

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

  it("uses a valid in-memory access token without refreshing", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(response({ username: "alice" }));
    const refresh = vi.fn();
    const request = createAuthenticatedRequester({
      getAccessToken: () => "valid-access",
      refreshAccessToken: refresh,
      onAccessToken: vi.fn(),
      onSessionExpired: vi.fn(),
    });

    await expect(request("/api/auth/me/")).resolves.toEqual({ username: "alice" });
    expect(refresh).not.toHaveBeenCalled();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("refreshes an expired access token and retries change-email exactly once", async () => {
    let access = "expired-access";
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(response({ detail: "Given token not valid for any token type" }, false, 401))
      .mockResolvedValueOnce(response({ email: "new@example.com", detail: "Email changed" }));
    const refresh = vi.fn().mockResolvedValue({ access: "replacement-access" });
    const request = createAuthenticatedRequester({
      getAccessToken: () => access,
      refreshAccessToken: refresh,
      onAccessToken: (replacement) => { access = replacement; },
      onSessionExpired: vi.fn(),
    });

    await expect(request("/api/auth/change-email/", {
      method: "POST",
      body: { email: "new@example.com" },
    })).resolves.toMatchObject({ email: "new@example.com" });
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[1][1]).toMatchObject({
      headers: expect.objectContaining({ Authorization: "Bearer replacement-access" }),
    });
    expect(access).toBe("replacement-access");
  });

  it("logs out with a safe message when refresh fails", async () => {
    const onSessionExpired = vi.fn();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      response({ detail: "Given token not valid for any token type" }, false, 401),
    );
    const request = createAuthenticatedRequester({
      getAccessToken: () => "expired-access",
      refreshAccessToken: vi.fn().mockRejectedValue(new Error("raw refresh error")),
      onAccessToken: vi.fn(),
      onSessionExpired,
    });

    await expect(request("/api/auth/me/")).rejects.toThrow(SESSION_EXPIRED_MESSAGE);
    expect(onSessionExpired).toHaveBeenCalledTimes(1);
  });

  it("does not loop when the retried request is also unauthorized", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      response({ detail: "Given token not valid for any token type" }, false, 401),
    );
    const request = createAuthenticatedRequester({
      getAccessToken: () => "expired-access",
      refreshAccessToken: vi.fn().mockResolvedValue({ access: "bad-replacement" }),
      onAccessToken: vi.fn(),
      onSessionExpired: vi.fn(),
    });

    await expect(request("/api/auth/me/")).rejects.toThrow(SESSION_EXPIRED_MESSAGE);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("shares one rotating refresh across concurrent unauthorized requests", async () => {
    let access = "expired-access";
    let releaseRefresh!: (value: { access: string }) => void;
    const pendingRefresh = new Promise<{ access: string }>((resolve) => { releaseRefresh = resolve; });
    const refresh = vi.fn().mockReturnValue(pendingRefresh);
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (_input, init) => {
      const authorization = (init?.headers as Record<string, string>)?.Authorization;
      return authorization === "Bearer expired-access"
        ? response({ detail: "Token is invalid or expired" }, false, 401)
        : response({ ok: true });
    });
    const request = createAuthenticatedRequester({
      getAccessToken: () => access,
      refreshAccessToken: refresh,
      onAccessToken: (replacement) => { access = replacement; },
      onSessionExpired: vi.fn(),
    });

    const requests = [
      request("/api/auth/me/"),
      request("/api/auth/resend-verification-authenticated/", { method: "POST" }),
    ];
    await vi.waitFor(() => expect(refresh).toHaveBeenCalledTimes(1));
    releaseRefresh({ access: "replacement-access" });

    await expect(Promise.all(requests)).resolves.toEqual([{ ok: true }, { ok: true }]);
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(4);
    expect(fetchMock.mock.calls.filter(([, init]) =>
      (init?.headers as Record<string, string>)?.Authorization === "Bearer expired-access",
    )).toHaveLength(2);
    expect(fetchMock.mock.calls.filter(([, init]) =>
      (init?.headers as Record<string, string>)?.Authorization === "Bearer replacement-access",
    )).toHaveLength(2);
  });

  it("shares one failed refresh and does not intercept or recursively retry it", async () => {
    const onSessionExpired = vi.fn();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      response({ detail: "Token is invalid or expired" }, false, 401),
    );
    const request = createAuthenticatedRequester({
      getAccessToken: () => "expired-access",
      refreshAccessToken,
      onAccessToken: vi.fn(),
      onSessionExpired,
    });

    const results = await Promise.allSettled([
      request("/api/auth/me/"),
      request("/api/auth/resend-verification-authenticated/", { method: "POST" }),
    ]);

    expect(results).toEqual([
      expect.objectContaining({ status: "rejected", reason: expect.any(SessionExpiredError) }),
      expect.objectContaining({ status: "rejected", reason: expect.any(SessionExpiredError) }),
    ]);
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/auth/refresh/")).toHaveLength(1);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(onSessionExpired).toHaveBeenCalledTimes(2);
  });
});
