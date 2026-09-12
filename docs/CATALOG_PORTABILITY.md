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

Catalog Portability does not add a native upload API or UI, image
transformations, or media garbage collection. T16 exposes the existing
ProductImage metadata through the storefront Product API and renders the
backend-selected image in the existing ProductCard; it does not introduce a
gallery or editing workflow.

## Catalog Portability v1 implemented behavior

The v1 capability is an explicit-Organization, trusted-operator workflow:

- `catalog_export` produces a deterministic package containing physical
  Products, ordered ProductImage metadata, and verified immutable media bytes.
- `catalog_validate` performs bounded archive/schema/media/planning validation
  without mutating catalog rows or storage.
- `catalog_import` applies `merge` or confirmed `replace-storefront` plans
  atomically under the Organization lock. Merge preserves destination-only
  Products; replace deactivates destination-only active Products.
- `catalog_reset_storefront` is a non-destructive, receipt-backed reset that
  deactivates active Products and preserves rows, images, media, and history.
- `catalog_dev_purge` is development-only, requires an exact confirmation and
  closed-world reference checks, deletes reviewed Product/Image graphs, and
  never deletes immutable media or resets sequences.
- `catalog_operation_status` reads a durable receipt for an operation ID.

Receipts are immutable, operation IDs are globally unique, retries with the
same input return the original receipt, and ambiguous commit outcomes fail
closed with `OUTCOME_UNKNOWN` unless a durable receipt can be recovered.
Organization locks, target digests, package digests, final-state checks, and
bounded errors protect against stale targets, concurrent writers, partial
mutation, and cross-Organization access.

Stock is live state by default: imports preserve destination stock. The
`restore-snapshot` policy is development-only and must be explicitly enabled;
production rejects snapshot restoration and destructive purge. Product and
ProductImage transport identity uses scoped UUIDv4 portable IDs, never local
primary keys.

Storefront responses expose ordered `images` metadata with adapter-generated
public URLs, alt text, sort order, and primary status. Explicit primary images
are first; otherwise the first domain-sorted image is presented. Empty image
sets are valid. Raw storage keys, package internals, credentials, and
cross-Organization or inactive Products are not exposed by the public API.
Imported media remains byte-exact and content-addressed; no garbage
collection occurs.

### Trusted operator command examples

Run these only from a trusted backend environment with
`CATALOG_PORTABILITY_ENABLED=true` and an explicit active Organization ID:

```bash
podman-compose exec -T web python manage.py catalog_export \
  --organization <ORG_ID> --output /secure/path/catalog.zip
podman-compose exec -T web python manage.py catalog_validate \
  --organization <ORG_ID> --input /secure/path/catalog.zip --mode merge
podman-compose exec -T web python manage.py catalog_reset_storefront \
  --organization <ORG_ID> --validate-only
podman-compose exec -T web python manage.py catalog_operation_status \
  --organization <ORG_ID> --operation-id <UUIDV4>
```

Import and reset apply commands require the plan's exact package/catalog
digests, a fresh UUIDv4, and the appropriate Organization confirmation. Purge
is restricted to disposable development data:

```bash
podman-compose exec -T web python manage.py catalog_import \
  --organization <ORG_ID> --input /secure/path/catalog.zip \
  --mode replace-storefront --operation-id <UUIDV4> \
  --expected-catalog-digest <DIGEST> \
  --confirm-package-sha256 <PACKAGE_SHA256> \
  --confirm-organization <ORG_ID>
podman-compose exec -T web python manage.py catalog_dev_purge \
  --organization <ORG_ID> --validate-only
```

Never run destructive commands against production. Preserve the JSON output
and receipt identifiers for recovery; on a lost acknowledgement, query
`catalog_operation_status` before retrying. A missing receipt after an
ambiguous commit is not permission to guess that a mutation failed.

## Final conformance and known exclusions

The repository's PostgreSQL tests cover deterministic package bytes, hostile
archives and media, Organization isolation, locking/concurrency, stale
targets, receipt idempotency and outcome recovery, reset/purge safety, and
storefront image presentation through reset/import round trips. Disposable
development UAT covers export, validate, reset, empty storefront, restore,
image presentation, purge, fresh restore, and operation-status behavior.

This repository does not contain Orders, OrderItems, checkout, carts, or
payments. Consequently, no claim is made that real order history was tested.
When those domains are introduced, their release must add integration tests
proving that Order/OrderItem history and historical snapshots remain unchanged
through merge, replace-storefront, reset, and purge; referenced catalog rows
are protected; and inventory writers use the common Organization locking
contract.

Hosted production media readiness remains an environment evidence concern:
the configured S3-compatible adapter, isolated credentials/bucket, explicit
jurisdiction, immutable `sha256/` retention, HTTPS custom domain, and required
cache/header policy must be verified in the deployment environment before
claiming production delivery readiness. The application contract does not
copy secrets into package data, logs, frontend code, or this document.
