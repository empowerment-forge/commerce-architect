import { apiGet } from "./client";

describe("apiGet", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("adds Authorization header when token is provided", async () => {
    const fetchMock = vi.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true }),
    } as Response);

    await apiGet("/api/products/", "token-123");

    expect(fetchMock).toHaveBeenCalledWith("/api/products/", {
      headers: { Authorization: "Bearer token-123" },
    });
  });

  it("does not add Authorization header when token is null", async () => {
    const fetchMock = vi.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true }),
    } as Response);

    await apiGet("/api/products/", null);

    expect(fetchMock).toHaveBeenCalledWith("/api/products/", {
      headers: undefined,
    });
  });

  it("calls the correct endpoint", async () => {
    const fetchMock = vi.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true }),
    } as Response);

    await apiGet("/api/products/");

    expect(fetchMock).toHaveBeenCalledWith("/api/products/", {
      headers: undefined,
    });
  });
});
