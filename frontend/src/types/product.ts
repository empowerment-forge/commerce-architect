export interface ProductImage {
  portable_id: string;
  url: string;
  alt_text: string;
  sort_order: number;
  is_primary: boolean;
}

export interface Product {
  id: number;
  name: string;
  description: string;
  product_type: string;
  price: string;
  is_active: boolean;
  created_at: string;
  images: ProductImage[];
}
