import { render, screen } from "@testing-library/react";

import { ProductCard } from "./ProductCard";
import type { Product } from "../types/product";

const mockProduct: Product = {
  id: 1,
  name: "Test Product",
  description: "Test Description",
  product_type: "service",
  price: "19.99",
  is_active: true,
  created_at: "",
  images: [],
};

describe("ProductCard", () => {
  it("renders product name", () => {
    render(<ProductCard product={mockProduct} />);

    expect(screen.getByText("Test Product")).toBeInTheDocument();
  });

  it("renders product description", () => {
    render(<ProductCard product={mockProduct} />);

    expect(screen.getByText("Test Description")).toBeInTheDocument();
  });

  it("renders formatted price", () => {
    render(<ProductCard product={mockProduct} />);

    expect(screen.getByText("$19.99")).toBeInTheDocument();
  });

  it("does not crash when description is empty", () => {
    render(
      <ProductCard
        product={{
          ...mockProduct,
          description: "",
        }}
      />,
    );

    expect(screen.getByText("No description available.")).toBeInTheDocument();
    expect(screen.getByText("Test Product")).toBeInTheDocument();
  });

  it("renders the backend-selected image and alt text", () => {
    render(
      <ProductCard
        product={{
          ...mockProduct,
          images: [
            {
              portable_id: "image-1",
              url: "https://media.example/sha256/example.jpg",
              alt_text: "A product portrait",
              sort_order: 0,
              is_primary: true,
            },
          ],
        }}
      />,
    );

    expect(screen.getByRole("img", { name: "A product portrait" })).toHaveAttribute(
      "src",
      "https://media.example/sha256/example.jpg",
    );
  });
});
