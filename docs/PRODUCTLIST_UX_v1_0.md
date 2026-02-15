
# PRODUCTLIST_UX.md
Version: 1.0
Status: Phase 1B Implementation Spec

---

# 1. Purpose

This document defines the implementation details for the first customer-facing screen:

Product Listing Page

This completes Phase 1B (Catalog UI).

This is NOT a general UX architecture document.
This is specific to this screen only.

---

# 2. Scope

This screen must:

- Fetch products from Django API
- Display active products
- Be responsive (mobile-first)
- Handle loading state
- Handle error state
- Be minimal and professional

This screen will NOT include:

- Cart
- Checkout
- Auth gating
- Filtering UI (Phase 1)
- Sorting UI (Phase 1)
- Pagination UI (Phase 1)

---

# 3. Data Source

Endpoint:

GET /api/products/

Response shape:

{
  id: number
  name: string
  description: string
  product_type: string
  price: string
  is_active: boolean
  created_at: string
}

Frontend must treat price as string.
Backend owns numeric precision and validation.

---

# 4. Component Structure

frontend/src/

types/product.ts
api/client.ts
api/products.ts
components/ProductCard.tsx
pages/ProductListPage.tsx

---

# 5. ProductListPage Behavior

On mount:

- Call getProducts()
- Set loading state
- Render grid after fetch
- Render error state if fetch fails

Grid layout:

- 1 column mobile
- 2 columns tablet
- 3 columns desktop

---

# 6. ProductCard Requirements

Must display:

- Product name (bold)
- Truncated description (2–3 lines)
- Price (visually emphasized)
- Clean card container
- Subtle hover shadow

No buttons in Phase 1.

---

# 7. UX States

Loading:

- Skeleton cards OR
- Centered loading indicator

Error:

- Friendly error message
- No crash
- No console spam

Empty:

- "No products available."

---

# 8. Tailwind Design Guidance

Background: slate-50
Cards: white + shadow-sm
Hover: shadow-md transition
Typography: clean sans-serif

Avoid:
- Gradients
- Excessive animations
- Decorative complexity

---

# 9. Definition of Done

- React project builds successfully
- TypeScript passes without errors
- API integration works
- Mobile layout verified
- No console warnings
- Django pytest still passes
- CI passes on PR

---

This screen represents the first public-facing UX surface of the platform.
It must be clean, stable, and minimal.
