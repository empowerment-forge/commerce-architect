import { render, screen, waitFor } from "@testing-library/react";

import { ProductListPage } from "./ProductListPage";

describe("ProductListPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("shows loading state while request is pending", () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      () => new Promise(() => {}) as Promise<Response>,
    );

    render(<ProductListPage />);

    expect(screen.getByText("Loading products...")).toBeInTheDocument();
  });

  it("renders products after successful fetch", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => [
        {
          id: 1,
          name: "Mock Product",
          description: "Mock Desc",
          product_type: "service",
          price: "10.00",
          is_active: true,
          created_at: "",
          images: [],
        },
      ],
    } as Response);

    render(<ProductListPage />);

    expect(await screen.findByText("Mock Product")).toBeInTheDocument();
    expect(screen.getByText("$10.00")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByText("Loading products...")).not.toBeInTheDocument();
    });
  });

  it("shows empty state when API returns no products", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => [],
    } as Response);

    render(<ProductListPage />);

    expect(await screen.findByText("No products available.")).toBeInTheDocument();
  });

  it("shows error state when fetch response is not ok", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 500,
    } as Response);

    render(<ProductListPage />);

    expect(
      await screen.findByText(
        "Unable to load products right now. Please try again later.",
      ),
    ).toBeInTheDocument();
  });
});
