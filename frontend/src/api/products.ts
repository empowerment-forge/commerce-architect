import { apiGet } from "./client";
import type { Product } from "../types/product";

export function getProducts(): Promise<Product[]> {
  return apiGet<Product[]>("/api/products/");
}
