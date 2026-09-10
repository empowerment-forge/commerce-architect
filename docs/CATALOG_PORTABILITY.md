# Catalog Portability v1 schema

This document freezes the T01 schema contract from the Catalog Portability v1
specification. It defines the data accepted by later portability packets; it
does not implement export, import, archive handling, image decoding, or any
database model.

## Package and manifest constants

The package is one ZIP containing `manifest.json`, `catalog.json`, and zero or
more content-addressed `media/` files. The v1 manifest has exactly these
values:

| Field | Value |
| --- | --- |
| `format` | `commerce-architect-catalog` |
| `format_version` | integer `1` |
| `domain_schema` | `product-commerce-catalog/1` |
| `entity_versions` | exactly `{ "product": 1, "product_image": 1 }` |
| `required_features` | sorted: `embedded-images`, `organization-scope`, `portable-identities`, `stock-snapshot` |
| `scope` | exactly `{ "kind": "organization", "coverage": "full" }` |
| `currency` | `USD` |
| `inventory_semantics` | `snapshot-not-reservation` |

The manifest also contains `counts` with exactly `products`,
`product_images`, and `media_files`, plus `files`. Each file descriptor has
exactly `path`, lowercase 64-character `sha256`, nonnegative `size_bytes`, and
`media_type`. `catalog.json` is `application/json`; image types are JPEG, PNG,
or WebP and their extensions must agree with their media types. The manifest
does not contain a package fingerprint, timestamp, database ID, organization
selector, host, or storage credential.

`catalog.json` is an object with exactly `products` and `product_images`, both
arrays. Every object field is required and non-null. Unknown fields are
errors. Product records are sorted by portable ID in canonical output; image
records are sorted by parent portable ID, sort order, and image portable ID.

## Field contracts

### Product

| Field | Contract |
| --- | --- |
| `portable_id` | Canonical lowercase hyphenated UUIDv4; persisted transport identity. |
| `sku` | 1–64 ASCII characters matching `[A-Z0-9][A-Z0-9._-]{0,63}`. |
| `name` | 1–255 Unicode characters and at least one non-whitespace character. |
| `description` | String, including empty; no more than 1 MiB UTF-8 bytes. |
| `price` | Canonical unsigned USD decimal string, exactly two fractional digits, `0.00`–`99999999.99`, no redundant leading zeroes, sign, or exponent. |
| `stock_quantity` | Integer `0`–`2,147,483,647`; booleans and floats are rejected. |
| `status` | Exactly `active` or `inactive`; later adapters map this to `is_active`. |

`product_type` and local audit timestamps are not serialized. This schema is
for physical Products; unsupported Product types must be rejected by later
adapters rather than omitted or coerced.

### ProductImage

| Field | Contract |
| --- | --- |
| `portable_id` | Canonical lowercase hyphenated UUIDv4 scoped to its parent Product. |
| `product_portable_id` | Portable ID of a Product in the same package. |
| `asset_path` | Exact `media/<lowercase-sha256>.<jpg|png|webp>` path; never a URL or storage key. |
| `alt_text` | String, including empty; no more than 2,000 Unicode characters. |
| `sort_order` | Integer `0`–`2,147,483,647`; equal values are allowed. |
| `is_primary` | JSON boolean. Each Product has at most one primary image. |

Zero Products, zero images, zero-image Products, and zero-primary Products are
valid. A shared `asset_path` is valid and represents one image binary reused by
multiple image records. Duplicate Product IDs, duplicate SKUs, or duplicate
image IDs under one Product are invalid. Image references to an unlisted
Product are invalid.

## Limits and error codes

The versioned maxima are: ZIP 520 MiB; total uncompressed member bytes 512
MiB; manifest 8 MiB; catalog JSON 16 MiB; 10,000 Products; 20,000 image
records; 50 images per Product; 20,002 regular-file entries; each image 10
MiB; 40 million decoded pixels; either image dimension at most 12,000; and
JSON nesting at most 16. Local configuration may lower, never raise, these
limits.

The stable error-code enum is:

`INVALID_PACKAGE`, `UNSUPPORTED_SCHEMA`, `INVALID_IMAGE`, `DUPLICATE_ID`,
`DUPLICATE_SKU`, `SKU_CONFLICT`, `UNSAFE_ARCHIVE`, `LIMIT_EXCEEDED`,
`MEDIA_UNAVAILABLE`, `STALE_TARGET`, `PACKAGE_CHANGED`, `CATALOG_BUSY`,
`IMPORT_FAILED`, `OUTCOME_UNKNOWN`, `REFERENCED_CATALOG`,
`OPERATION_NOT_ALLOWED`, and `OPERATION_ID_CONFLICT`.

T01 validation reports schema errors without mutating database rows or durable
media. Later packets must preserve these codes and reject unsupported versions,
features, fields, and values; they must not silently repair or downgrade input.

## Conformance fixture inventory

The fixture directory contains explicit expected outcomes used by
`backend/tests/test_catalog_portability_schema.py`:

| Fixture | Expected outcome | Contract coverage |
| --- | --- | --- |
| `valid/empty_catalog.json` | valid | Minimal empty catalog. |
| `valid/product_without_images.json` | valid | One Product with no images. |
| `valid/shared_image_binary.json` | valid | Active/inactive Products sharing one binary path. |
| `valid/boundary_values.json` | valid | Exact maximum stock, price, sort order, and boundary Unicode values. |
| `invalid/unknown_product_field.json` | `INVALID_PACKAGE` | Unknown field rejection. |
| `invalid/duplicate_product_id.json` | `DUPLICATE_ID` | Duplicate portable identity rejection. |
| `invalid/float_stock.json` | `INVALID_PACKAGE` | Float-as-integer rejection. |
| `invalid/boolean_stock.json` | `INVALID_PACKAGE` | Boolean-as-integer rejection. |
| `invalid/unknown_feature_manifest.json` | `UNSUPPORTED_SCHEMA` | Required-feature compatibility rejection. |

The schema module also rejects duplicate JSON object keys and non-standard
JSON constants such as `NaN`. Archive structure, byte hashes, image decoding,
and transport behavior are deliberately deferred to later packets.

## Verified immutable media boundary

Catalog image handling preserves the original verified JPEG, PNG, or WebP
bytes under the provider-neutral key `sha256/<lowercase-sha256>`. Verification
enforces the v1 byte, dimension, and decoded-pixel limits, derives media type
from decoding, forces complete pixel loading, and completes for every package
image before any durable write begins.

The storage boundary exposes only conditional create-if-absent and verified
read operations. A successful write or reuse requires authenticated readback of
the exact bytes and required metadata. Existing content is never overwritten,
renamed, or deleted to resolve a conflict. `ProductImage.storage_key` stores
only the provider-neutral key; provider URLs, bucket names, credentials, SDK
responses, and signed URLs do not enter catalog models or package data.

Local development uses persistent filesystem media with cross-process locking
and a development-only GET/HEAD route. Hosted deployments use an explicitly
configured S3-compatible adapter and public delivery origin. The hosted media
contract requires isolated environment credentials and buckets, immutable
retention protection for `sha256/`, HTTPS, canonical response metadata,
`X-Content-Type-Options: nosniff`, successful-object caching without negative
caching, and read-only public delivery.

This boundary does not add import/export services, a native upload API or UI,
image transformations, garbage collection, or storefront image presentation.
