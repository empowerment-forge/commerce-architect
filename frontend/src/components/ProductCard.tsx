import type { Product } from "../types/product";

interface ProductCardProps {
  product: Product;
}

function truncateDescription(description: string, maxLength = 120): string {
  if (description.length <= maxLength) {
    return description;
  }

  return `${description.slice(0, maxLength).trimEnd()}...`;
}

export function ProductCard({ product }: ProductCardProps) {
  const selectedImage = product.images[0];

  return (
    <article className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm transition-shadow duration-200 hover:shadow-md">
      {selectedImage ? (
        <img
          className="mb-4 aspect-square w-full rounded-md object-cover"
          src={selectedImage.url}
          alt={selectedImage.alt_text}
        />
      ) : null}
      <h2 className="mb-2 text-lg font-bold text-slate-900">{product.name}</h2>
      <p className="mb-4 text-sm leading-6 text-slate-600">
        {truncateDescription(product.description || "No description available.")}
      </p>
      <p className="text-xl font-semibold text-slate-900">${product.price}</p>
    </article>
  );
}
