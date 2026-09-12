# Catalog Portability — proposed v1 implementation specification

Status: design for review; no implementation authorized by this document. Prepared 2026-09-09 against repository commit `e322b551ef5a14ba3a1e5f7ca8877151363ed3f3`.

## Source authority and implementation baseline

The following existing domain specifications were read and govern this proposal:

- [Product Commerce Model Overview](https://docs.google.com/document/d/1IQOt7_CXflqbFxRzJ9lSrKLAUFgHW0OEG6cpePL26oc/edit): physical-product commerce, Organization ownership, USD MVP, and historical transaction integrity.
- [Product](https://docs.google.com/document/d/1zUlVYxK0RZdAFVW7_N5_6kmP8ExfLue578FXN1-yg6s/edit): Organization-scoped SKU, current price, stock, availability, and separate images.
- [ProductImage](https://docs.google.com/document/d/1cuJJo-xNuEJZ7UkqJUf8HM3yWleDb7WQ3XDokjqSs1Q/edit): storage reference, alt text, ordering, at most one primary image, and storage independence.
- [Organization](https://docs.google.com/document/d/1o0Z_lLkxJwHq0tcigI8DD1NtOLgm5nSCdryHFINmo2k/edit): business/tenancy boundary.
- [Browse & Shop](https://docs.google.com/document/d/1L9CpGqwKAiixvvwyimC6XnhL9AUJ0snrcqJ3trmGr8U/edit): public browsing within the current Organization context.
- [Order](https://docs.google.com/document/d/15ghzi0G4M9x1u8dFmJSPAJLQhi6AvyZ-dfjDM6Souwo/edit) and [OrderItem](https://docs.google.com/document/d/1OAwTDoPlezITHf0KURBRFis7O1gCnTG_sdkXW1SFGOU/edit): durable sale snapshots, independent of later Product changes.
- [Checkout](https://docs.google.com/document/d/1kFoWNhG44A4fnr3PlBknceRBBjgl0xQ8qYQjzkcGjgM/edit) and [Cart Management](https://docs.google.com/document/d/1IsFNRqAt3koVOfzwODcs_f_cAsqLTHFKU-36eo5IAdA/edit): mutable shopping intent, checkout revalidation, and inventory protection.

The current repository is substantially earlier than that specified domain. Its [Product model](/home/forge/dev/repos/commerce-architect/backend/catalog/models.py) has name, description, physical/service type, decimal price, `is_active`, and creation time. It has no Organization, SKU, stock, ProductImage, Cart, or Order implementation. The [current architecture](/home/forge/dev/repos/commerce-architect/docs/ARCHITECTURE.md) places business rules in Django models/services, exposes a public product list, and uses PostgreSQL. The [testing strategy](/home/forge/dev/repos/commerce-architect/docs/TESTING_STRATEGY.md) requires actual PostgreSQL integration tests.

Consequently, Product Commerce catalog foundations are explicit prerequisites below. Their absence must not be concealed by exporting an unscoped, reduced representation and calling it the specified capability. Orders, checkout, payments, and fulfillment need not be implemented to ship portability.

## 1. Capability boundary

Catalog Portability exports and restores the current catalog of exactly one explicitly selected Organization. A full package includes every Product in that scope, active and inactive, each Product's complete image collection, and the exact referenced image bytes. All v1 Products in this scope must be physical Products.

It owns the format, compatibility rules, validation, target reconciliation, atomic catalog mutation, operation receipts, and production-safe storefront reset. Operator interfaces call the same domain services. V1 exposes management commands to trusted installation operators; a browser operator experience is deferred.

It excludes database backup/restore, database identities/sequences, Organizations themselves, Organization configuration, users/permissions/secrets, Customers, Carts, Orders and snapshots, payments/refunds, fulfillment, themes, and infrastructure provisioning. It neither reconstructs commerce history nor transfers ownership of that history.

Stock is exported because it is a Product field, but applying a historical stock snapshot is separate from importing descriptive catalog data. See section 3.

“Exact restore” means the same portable identities, SKUs, names, descriptions, prices, active states, image metadata/order/bytes, and—when expressly selected and permitted—stock quantities. It does not mean identical database primary keys, local audit timestamps, generated image URLs, infrastructure, or page pixels. Consistent rendering additionally requires compatible storefront code. No cross-installation promise depends on incidental database row order.

A full export after replace-storefront can contain additional inactive destination Products retained for history. Replace makes the visible Product catalog match the package; it does not make the destination's retained database history identical to the source.

## 2. Export package specification

### 2.1 Exact structure

One ZIP file, conventionally named `catalog.ca-catalog.zip`, containing:

```text
manifest.json
catalog.json
media/<lowercase-sha256>.jpg
media/<lowercase-sha256>.png
media/<lowercase-sha256>.webp
```

Only the first two files are mandatory when there are no images. Each distinct image binary appears once, using the suffix dictated by its verified media type. No explicit directory entries, optional attachments, scripts, thumbnails, URLs, nested archives, or extra files are allowed. This is a format layout, not executable code.

### 2.2 Manifest: all fields required

| Field | Exact v1 rule |
|---|---|
| `format` | String `commerce-architect-catalog` |
| `format_version` | Integer `1` |
| `domain_schema` | String `product-commerce-catalog/1` |
| `entity_versions` | Object containing exactly `product: 1` and `product_image: 1` |
| `required_features` | Sorted array containing exactly `embedded-images`, `organization-scope`, `portable-identities`, `stock-snapshot` |
| `scope` | Object containing exactly `kind: organization` and `coverage: full` |
| `currency` | String `USD` |
| `inventory_semantics` | String `snapshot-not-reservation` |
| `counts` | Object with integer `products`, `product_images`, `media_files` |
| `files` | Array of descriptors for `catalog.json` and every media file; excludes the manifest itself |

Each file descriptor contains exactly `path`, `sha256` (64 lowercase hex characters), `size_bytes` (nonnegative integer), and `media_type`. Catalog media type is `application/json`; image types are `image/jpeg`, `image/png`, or `image/webp`. File descriptors are sorted by ASCII path. Sizes, hashes, counts, and actual archive members must agree exactly.

Do not put database IDs, source hostnames, storage bucket names, credentials, or a destination Organization selector in the manifest. Target Organization is always selected outside the package. The manifest does not create or rename an Organization.

No export timestamp, random export ID, or application build number is embedded. Those belong in the export receipt; omitting them permits identical exports to have identical bytes. Compatibility is defined by the explicit format/domain/entity contracts, not by a marketing release or Django migration version. The SHA-256 of the complete ZIP is the package fingerprint used in previews and receipts; it is not embedded recursively in the ZIP.

### 2.3 Catalog: exact fields

`catalog.json` is an object with exactly `products` and `product_images`, both arrays, including when empty. Unknown object fields anywhere are errors in v1. Every listed field below is required; null is forbidden.

| Product field | Representation and validation |
|---|---|
| `portable_id` | Canonical lowercase, hyphenated UUIDv4, persisted on Product |
| `sku` | 1–64 ASCII characters; `[A-Z0-9][A-Z0-9._-]{0,63}` |
| `name` | 1–255 Unicode characters; must contain a non-whitespace character |
| `description` | String, including empty; at most 1 MiB UTF-8 |
| `price` | USD decimal string with exactly two fractional digits, no sign/exponent; range `0.00`–`99999999.99`; no redundant leading zeroes |
| `stock_quantity` | Integer 0–2,147,483,647; booleans are not integers |
| `status` | Exactly `active` or `inactive` |

`status` maps to the existing `is_active` field. Do not introduce a second writable availability field. `product_type` is not serialized: this schema describes physical Products only. The adapter must reject unsupported source/target Product types rather than omit or coerce them.

| ProductImage field | Representation and validation |
|---|---|
| `portable_id` | Canonical UUIDv4 persisted on ProductImage |
| `product_portable_id` | Reference to a Product in this package |
| `asset_path` | Exact listed media path; no URL or source storage key |
| `alt_text` | String, including empty; at most 2,000 Unicode characters |
| `sort_order` | Integer 0–2,147,483,647 |
| `is_primary` | Boolean |

A Product can have zero images and zero primary images. More than one primary image is invalid. Equal sort_order values are allowed; ascending image portable ID breaks ties. The display order is `(sort_order, portable_id)`; primary selection is independent of display order. If a storefront needs a representative image without an explicit primary, use the first in display order.

Local Product/ProductImage `created_at` and `updated_at` are not portable fields. Existing creation times remain unchanged; imported new rows receive local creation times; changed rows receive a local update time; unchanged rows are not saved. Exporting them as reusable local audit facts would confuse catalog restoration with database restoration.

SKU syntax is a proposed concrete validation rule for the presently unimplemented SKU field, not a claim that the authoritative document already specifies case handling. Store only canonical uppercase SKUs; require canonical input in packages and bootstrap maps. Do not trim, case-convert, round prices, or otherwise repair imported data silently.

### 2.4 Identity

Product identity is `(target Organization, product portable_id)`. ProductImage identity is `(parent Product identity, image portable_id)`; its image UUID is scoped to its parent. Consequently, duplicate image IDs under one parent are invalid, while the same UUID under a different parent is a distinct image identity. No operation reparents an existing image row.

Generate UUIDs once when native entities are created, backfill existing Products once, and preserve imported UUIDs on every subsequent export. Enforce Product uniqueness on `(organization, portable_id)` and SKU uniqueness on `(organization, sku)`, including inactive Products. Enforce image uniqueness on `(product, portable_id)`.

Portable identity is necessary because database IDs cannot identify an entity across installations and SKU is a mutable business identifier. This adds a transport identity to existing entities; it does not introduce a replacement `item_id` domain concept, serialized-unit identity, or duplicate Product entity.

The same package can be imported into two Organizations on one installation without global UUID or SKU conflicts. A copied Product and its later import remain related within each explicitly selected target scope. Names, prices, and SKU equality alone never establish identity.

### 2.5 Determinism and compatibility

- Sort Products by portable ID. Sort image records by parent portable ID, sort_order, and image portable ID. Never order by database ID, insertion order, or locale collation.
- JSON is UTF-8 without BOM, with lexicographically sorted keys, no insignificant spaces, literal Unicode, standard JSON escaping, and exactly one trailing LF. Preserve string content and Unicode normalization; reject invalid Unicode. No floats, NaN, Infinity, duplicate keys, or unpaired surrogates.
- Canonical ZIP output uses stored entries without compression, manifest first, catalog second, then media paths in ASCII order; fixed DOS timestamp 1980-01-01 00:00:00; Unix creator system 3, creator/extractor version 20, general-purpose flags 0, internal attributes 0, and external attributes equal to regular-file mode 0100600 shifted left 16 bits. CRC and sizes are written in the headers; no data descriptors. Archive/member comments and extra fields are empty; no ZIP64 or split archives. Freeze these header attributes in a golden fixture. No environment-specific metadata.
- Import accepts only this stored-file profile, but does not require member order, canonical whitespace, or canonical JSON key order. Values must still meet the canonical field rules. Re-export produces canonical bytes.
- A package with a different format version, domain schema, entity version, unknown feature, missing required feature, or unsupported extension fails before mutation. There is no v1 “best effort” downgrade.
- Installations with future required catalog entities must reject v1 full import/export until a reviewed adapter can represent them losslessly. Never silently discard variants, category relationships, or other required data. No generic plugin loader or automatic migration framework in v1.

Maintain a small explicit compatibility module listing supported Product/ProductImage concrete fields, catalog-owned relations, external reference checks, and inventory-protection integration. Compare it against the installed model registry; an added concrete field or relation without a declared disposition blocks portability until reviewed. This module is code owned by the installation, never supplied by a package. In the present baseline it declares no implemented inventory protections; after checkout adds them, a registered check must answer whether any are active. An unknown integration never means “none active.”

## 3. Import modes and reconciliation

Every operation names an existing target Organization explicitly. There is no default-to-first-Organization behavior. V1 commands are enabled for an active target Organization with a supported physical Product catalog; unsupported Product types in the target fail the operation. An empty Product catalog is valid.

### Common planning and conflict rules

Completely validate the archive, schema, references, all image bytes, and the target-dependent plan before changing domain rows or durable media. Preview reports target Organization, package fingerprint, target catalog digest, inventory policy, counts and portable IDs of creates/updates/no-ops/removals/deactivations, and every conflict. Bound displayed errors to 100, sort by record identity/path and error code, and indicate truncation. Any error fails the entire operation.

The target digest hashes a canonical snapshot of all target Product and ProductImage portable fields, current stock, and image content hashes. It excludes local audit times. Preview is advisory; apply validates again and recomputes the plan under the target Organization lock. Apply requires both the preview's target digest and the exact package fingerprint. A mismatch returns `STALE_TARGET` or `PACKAGE_CHANGED`, with no catalog mutation.

Product reconciliation:

| Destination condition | Result |
|---|---|
| No matching UUID and incoming SKU unused | Create Product with incoming UUID |
| Matching UUID and same SKU | Update imported fields, subject to stock policy |
| Matching UUID and changed SKU, new SKU unused by any other destination Product | Update SKU; retain database row and identity |
| Incoming SKU belongs to another UUID, even if that row is inactive or will be deactivated | `SKU_CONFLICT`; fail entire import |
| Duplicate Product UUID or SKU inside package | `DUPLICATE_ID` / `DUPLICATE_SKU`; fail entire import |
| Same UUID and same effective values | No-op; do not change timestamps |

Conservative v1 rule: an incoming SKU must not be owned by another destination Product at the start of apply. Reject simultaneous SKU swaps and cycles rather than invent temporary SKUs. There is no overwrite, rename-on-conflict, UUID regeneration, automatic matching by SKU, or force flag.

For each incoming Product, its package image collection is authoritative in both modes. Match image identities and update metadata/content references, insert new images, and remove image rows omitted from that incoming Product's image set. An empty set removes that Product's image associations. This is safe because ProductImage is catalog data, not an Order snapshot. Physical media bytes are not deleted. If a future external record references an image row, removal must be protected and fail pending an explicit compatibility decision.

### Validate-only

Validate against a specified intended mode (`merge` or `replace-storefront`) and selected stock policy. Return the complete bounded plan or errors. Do not write Product, image, receipt, or other database rows; do not write to durable media storage or change existing files. Private temporary read/staging files are permitted and cleaned up. Validate-only cannot promise the destination will remain unchanged afterward.

### Merge

Apply incoming Product fields and complete image sets. Preserve every destination Product absent from the package, including its visibility and images. Incoming inactive Products become/remain inactive. An empty package is a valid no-op.

Expected outcome: all incoming Product aggregates match their imported effective values, and unrelated target Products remain unchanged.

### Replace storefront

Perform the same incoming aggregate reconciliation as merge. Additionally set `is_active=False` on every destination Product absent from the package. Retain those rows, portable identities, SKUs, stock, image rows, and media.

Expected outcome: the set of active Product identities is exactly the package's active set. An empty package deactivates the entire target Product storefront. Replace requires explicit confirmation of the target Organization and package fingerprint. It never hard-deletes a Product.

### Inventory policy: explicit and independent of mode

Default `preserve`: keep stock of matching Products; create new Products with stock zero. Preview explicitly reports all package stock values that will not be applied. Activation remains the package's availability state; stock zero must remain non-purchasable under checkout inventory validation.

Optional `restore-snapshot`: set stock of incoming Products to package quantities. This requires `COMMERCE_ENV=development`, a separately enabled `CATALOG_ALLOW_SNAPSHOT_STOCK_RESTORE` setting defaulting to false, explicit command selection, and no active inventory protections for the target. Production always rejects it even if the flag is enabled. Hosted development that runs production security settings must also reject it; environment labels or DEBUG are not substitutes for these guards.

For the motivating soft-reset/restore scenario, default preserve already keeps unchanged stock. Use restore-snapshot only when intentionally rewinding a development catalog. Importing into a fresh production installation creates zero stock until normal inventory administration establishes current quantities. V1 does not overwrite production inventory from an old catalog export.

### Transaction and concurrency boundary

1. Read a bounded immutable local copy of the package; validate every member and the initial plan.
2. Write validated image bytes through the configured storage adapter to immutable content-addressed keys. Reuse only objects whose hash and length verify. Finish and verify durable writes before referencing them from domain rows. Failure here leaves the catalog unchanged.
3. Begin one outer database transaction. Lock the target Organization, recheck policy/compatibility, package fingerprint, current digest, conflicts, and all mutation preconditions. Check media readiness before mutating rows.
4. Apply Products, then image associations and primary-image changes, then replace deactivations; write the successful operation receipt in the same transaction. Validate final aggregate constraints before commit. Never commit per Product.
5. Return success only after commit. Publish any optional cache invalidation after commit. Do not make image promotion or any required part of success depend on an after-commit callback.

`atomic()` protects database changes; after-commit callbacks cannot make an external storage write part of that transaction. This design deliberately completes immutable storage writes first. See [Django transaction semantics](https://docs.djangoproject.com/en/6.0/topics/db/transactions/).

A failed transaction or process crash may leave unreferenced immutable media objects. Those are harmless storage residue, not partially imported catalog state. V1 does not garbage-collect them. Never delete an object during rollback because another committed catalog or concurrent import may reference it. A DB row must never commit pointing at a merely temporary object.

All application catalog writers—including Django admin, bootstrap, reset, import, and future stock/checkout writers—must acquire the same Organization row lock before reading or changing catalog state. Product locks, if needed, follow in portable-ID order. This prevents insert races and empty-catalog races that locking only existing Products misses. Use a five-second lock timeout and return `CATALOG_BUSY` on timeout. PostgreSQL releases transaction locks at transaction end; follow its [explicit locking rules](https://www.postgresql.org/docs/16/explicit-locking.html).

This guarantee covers supported application writers, not arbitrary privileged SQL or storage deletion outside the application. Future checkout/payment integration must participate before enabling those writers. An in-flight checkout remains an Orders/inventory responsibility; portability cannot cancel obligations or release reservations by itself.

Successful apply/reset commands require a caller-generated `operation_id` UUID. Store a receipt with Organization, operation type, package fingerprint if applicable, stock policy, before/after digests, action counts, and completion time. Retrying the same ID and identical semantic inputs returns the original receipt without replaying mutation—even if the catalog has since changed. Reusing it with different target/action/package/policy/precondition is `OPERATION_ID_CONFLICT`. A unique constraint settles concurrent duplicate attempts. No credentials or full package content belong in the receipt.

After a connection loss around commit, report an unknown outcome until the receipt is read using that operation ID. Do not claim rollback without evidence or issue a compensating delete. Validation-only and failed operations write no receipt; bounded operational logs can record failure codes.

## 4. Reset semantics

### Production-safe storefront reset

Within one target-scoped transaction and the common lock, set every active Product inactive. Preserve Product IDs/UUIDs/SKUs, descriptive fields, stock, images, and all external records. Require a preview digest, explicit target confirmation, and operation ID. A second reset is a successful no-op.

An empty browse result is the goal. Existing carts remain; checkout must revalidate their now-inactive Products. Do not clear carts, cancel Orders, refund payments, change fulfillment, or delete files. Existing OrderItems retain their Product references and historical snapshots. Product reactivation later does not change any past transaction.

### Development-only destructive catalog reset

A separately named `catalog_dev_purge` command is allowed only with `COMMERCE_ENV=development`, `CATALOG_ALLOW_DESTRUCTIVE_RESET=true` (default false), a target preview digest, and the literal confirmation `PURGE-CATALOG:<organization-id>`. No production/API/admin action exposes it. Production rejects it regardless of DEBUG or supplied confirmations.

Delete only the selected Organization's ProductImage and Product rows, atomically. Never delete Organizations, accounts, receipts, Carts, Orders, or other commerce records; never reset database sequences. Before deletion, fail if any target Product or image has any reference from outside that deletion set, including CartItems, OrderItems, generic references, or an unknown extension. Do not rely on a cascading delete collector to decide what is safe.

If durable or mutable commerce references exist, use soft reset. A whole-environment database wipe remains a separate developer/infrastructure procedure outside this capability. Purge retains media bytes and operation receipts. Catalog-level restore after purge may allocate new primary keys; this is acceptable only because the purge could not delete referenced Products.

Unknown future reference mechanisms must fail compatibility checks until explicitly covered. The preflight reference check and deletion must execute under the common write protocol; database FK protection remains a final backstop. Future OrderItem references should use protective deletion behavior for this feature, never cascade from Product into Order history.

## 5. Explicit, testable invariants

1. **Scope isolation:** applying, replacing, resetting, or purging Organization A changes no Product, image, stock value, or receipt belonging to Organization B.
2. **Complete export:** an export includes every supported active and inactive Product in the selected Organization and every associated image; no unsupported record is silently skipped.
3. **Portable identity:** exporting twice preserves UUIDs; import into a database with different primary keys preserves portable identity; repeated apply creates no duplicate aggregates.
4. **SKU ownership:** two Products in one Organization cannot share a canonical SKU, including inactive Products; equal SKUs in different Organizations are allowed.
5. **Validation purity:** validate-only performs zero database writes and zero durable media writes on both successful and failed validation.
6. **Atomic mutation:** failure after any inserted/updated/deactivated Product, image removal, primary-image switch, or receipt insert leaves all catalog database rows equal to their pre-operation values.
7. **Image readiness:** every committed imported image reference resolves to complete bytes with the declared SHA-256; a failed object write causes no catalog mutation.
8. **Image cardinality:** every image has one parent; no Product has more than one primary image; zero-image and zero-primary Products are valid.
9. **Merge isolation:** destination Products absent from a merge package are byte-for-byte unchanged in all stored fields.
10. **Replace visibility:** after replace, target active portable IDs equal package active portable IDs; destination-only Products remain with their original PK, UUID, SKU, stock, and image associations.
11. **Safe reset:** after reset, target active count is zero; all other Product data, image rows, and external references remain unchanged, except update times on changed Products.
12. **History preservation:** Order/OrderItem/OrderAddress, adjustments, Payments, Refunds, Fulfillments, and Customer records are unchanged by portability, including sale amounts, snapshots, states, and references.
13. **Inventory policy:** preserve never changes existing stock and creates new stock at zero; restore-snapshot applies exact package stock only under its development guards.
14. **Content idempotence:** repeating an identical import against unchanged catalog state produces no new Product/image rows and changes no entity audit timestamps. Distinct successful operation IDs may create distinct receipts.
15. **Request idempotence:** retrying one successful operation ID returns its original receipt without reapplying it; changed inputs with that ID fail.
16. **Deterministic export:** identical domain state and image bytes produce identical ZIP bytes regardless of database IDs, query insertion order, wall clock, or source host.
17. **Stable planning:** any target content change after preview causes apply with the old digest to fail before domain mutation.
18. **Concurrent integrity:** two imports with one preview digest serialize; after one effective change commits, the other fails stale validation. Concurrent creation in an initially empty catalog cannot bypass the Organization lock.
19. **Purge protection:** one external reference blocks the entire purge; no cascading deletion of external rows occurs.
20. **Environment enforcement:** production and hosted development using production settings cannot perform destructive purge or snapshot stock restoration, regardless of DEBUG or override flags.
21. **Restore demonstration:** export a development catalog; soft reset; replace using that package; compare all portable fields and images, and the active identity set, to the original. With restore-snapshot enabled, stock also matches exactly. Existing database identities are retained.
22. **Fresh destination demonstration:** import into an empty compatible development Organization using restore-snapshot; canonical re-export equals the original ZIP byte-for-byte, although database IDs and audit times may differ.

## 6. Failure cases and security

### Bounded input profile

V1 hard limits: ZIP file 520 MiB; total uncompressed member bytes 512 MiB; manifest 8 MiB; catalog JSON 16 MiB; 10,000 Products; 20,000 image records; 50 images per Product; at most 20,002 regular-file entries; each image 10 MiB; decoded image at most 40 million pixels and neither dimension above 12,000. JSON nesting at most 16 levels. Enforce actual streamed bytes, not just claimed ZIP sizes. Local configuration may lower limits, but may not raise these versioned maxima.

Accept only single-frame JPEG, PNG, and WebP verified by a maintained decoder; reject animation, SVG, HTML, mismatched extension/type, malformed/truncated images, and decompression-bomb warnings. Fully decode for validity, but retain original bytes; no image transformation in v1. Include the decoder dependency in the existing locked dependency workflow. Production media must be served with verified content type and `nosniff`, without application execution.

Stored-only ZIP entries avoid compressed ZIP bombs; decoded image and total resource limits remain necessary. Reject encrypted, compressed, split, ZIP64, symlink, device, and directory entries; duplicate member names; absolute paths; `..`; backslashes; NUL/control characters; drive-letter/UNC paths; and any name outside the exact manifest/catalog/media grammar. Reject case aliases and local/central-header inconsistencies. Never call unrestricted archive extraction. Read allowed entries into owned private temporary files with generated local names. The [Python ZIP documentation](https://docs.python.org/3/library/zipfile.html) explains why untrusted archive handling needs explicit care.

### Failure contract

| Condition | Required result |
|---|---|
| Invalid JSON, duplicate keys, missing/unknown fields, wrong types or ranges | `INVALID_PACKAGE`; no domain/durable-media writes |
| Unsupported format/domain/entity/features | `UNSUPPORTED_SCHEMA`; no fallback |
| Missing/extra member, wrong size/hash, missing image parent, invalid primary count | `INVALID_PACKAGE`; no partial acceptance |
| Corrupt or unsupported image | `INVALID_IMAGE`; fail whole package |
| UUID/SKU conflict | Stable conflict code and record identity; no automatic repair |
| Unsafe archive path/type/structure | `UNSAFE_ARCHIVE`; no extraction outside private staging |
| Input/resource limit exceeded | `LIMIT_EXCEEDED`; stop reading promptly |
| Unsupported storage adapter or unavailable/corrupt durable object | `MEDIA_UNAVAILABLE`; no catalog commit |
| Target changes after preview / package changes | `STALE_TARGET` / `PACKAGE_CHANGED` |
| Lock timeout | `CATALOG_BUSY`; rollback; operator may validate and retry |
| Database constraint or transaction failure | `IMPORT_FAILED`; whole transaction rolls back |
| Lost commit acknowledgement | Resolve by operation receipt; until then `OUTCOME_UNKNOWN` |
| External reference during purge | `REFERENCED_CATALOG`; no deletion |
| Forbidden environment or disabled command | `OPERATION_NOT_ALLOWED`; no mutations |

Hashes establish internal integrity, not who authored a package. Packages are untrusted even when hashes match. Import makes no external network requests based on package content: no URL image fetching, SSRF, remote schema loading, template execution, pickles, dynamic model loading, SQL, or executable hooks. The only network I/O allowed is the installation's preconfigured database and storage services.

V1 command access is an infrastructure permission: only trusted operators with the installation's execution and credential access may run it. Do not pretend `--user` or `--actor` authenticates a person. No catalog upload/import/reset HTTP endpoint is added, and ordinary storefront/JWT users cannot invoke these commands through the application. This v1 does not offer delegated merchant self-service; an API/UI later requires Organization-scoped authorization, upload controls, CSRF where appropriate, and auditable authenticated identity.

While Organization-aware operator permissions do not yet exist, any newly exposed catalog/Organization admin management is limited to active superusers. Existing staff status alone is insufficient. Public browsing stays unauthenticated but is restricted to the configured storefront Organization. No user-supplied Organization query parameter selects another storefront in v1.

Export files and private staging use 0600 files in 0700 directories. Export writes a temporary sibling and publishes the completed file without overwriting an existing destination; a failed export leaves no final package. Logs contain operation ID, scope, fingerprints, counts, and bounded codes—not package contents, storage credentials, signed URLs, or a full filesystem dump. No package verification option can disable security checks.

## 7. Smallest coherent v1

V1 includes the required Organization/catalog foundations; persistent portable identities; full physical Product and ProductImage bundles; strict JSON/ZIP/image validation; validate-only, merge, replace-storefront; soft reset; separately guarded development purge and stock snapshot restoration; target isolation; concurrency controls; atomic database import; immutable media storage; durable operation receipts; and a trusted-operator command interface with PostgreSQL tests.

Use one active storefront Organization selected by configuration. Support multiple Organizations in data isolation and explicit command targets without adding multi-tenant host routing, membership management, or a tenant UI. Preserve existing public Product API fields, adding only the catalog fields needed for the specified baseline and image rendering. No portability-specific frontend page is required.

Defer browser upload/download UI, background jobs, huge-catalog streaming/resumption, partial exports, CSV/third-party import, fuzzy matching, automated schema conversion, variants/categories, advanced inventory, production stock snapshot overwrite, signing/encryption, media garbage collection, and generalized extension frameworks.

Image support must work with configured durable storage; production must not silently fall back to an ephemeral container filesystem. Portability defines the immutable storage contract. Choosing and configuring the actual production media backend is a deployment prerequisite, not authority to provision infrastructure during implementation.

## 8. Useful later enhancements

- Organization-authorized operator UI with saved previews and job progress.
- Reviewed schema adapters for variants/categories and external catalog migrations.
- Signed/encrypted packages when sharing catalogs across trust boundaries.
- Large-catalog jobs and safe reconciliation of unreferenced media.
- Explicit inventory transfer workflows backed by the future inventory domain.

## 9. Genuine decisions still requiring human input

These are not generic requests to approve routine coding choices. They depend on facts or policies absent from the authoritative documents and checkout.

| Decision | Recommended default | Rationale / gate |
|---|---|---|
| Ownership, canonical SKU, and starting stock for existing rows | Supply a reviewed per-row bootstrap mapping to a named Organization; use zero stock where no actual count exists | Existing rows contain none of these facts, so an agent must not invent merchant ownership or inventory; blocks final non-null migration on populated installations |
| Existing legacy `service` rows, if any | Keep them out of the physical Product Commerce migration and resolve them in a separately approved Service Commerce migration | Reclassifying or dropping services would violate the authoritative physical Product boundary; blocks claiming full catalog portability for an affected target |
| Production media backend and persistence | Use the installation's approved durable object-storage backend behind the immutable adapter; use a persistent local backend only for development/tests | No production media service is configured in this checkout, so code alone cannot establish durable cross-instance media availability |

The remaining choices in this document—including UUID transport identity, CLI-first delivery, conservative SKU conflicts, inventory preservation, format limits, and soft-reset semantics—are proposed settled defaults. Reviewers can change them before acceptance; Luna must not redesign them while coding. If a decision changes, update the contract and tests first.

## 10. Implementation work packets for Luna Medium

Paths below are proposed unless identified as existing. All repository paths are absolute. For every task, “no interface” means no new API endpoint or management command; “no migration” means no database migration. Do not create provisional stubs that silently skip later invariants. Keep the feature disabled until the release acceptance packet passes.

### T01 — Freeze the accepted schema and conformance fixtures

- **Objective:** make this contract executable input for later packets after resolving the applicable decisions in section 9.
- **Files:** `/home/forge/dev/repos/commerce-architect/docs/CATALOG_PORTABILITY.md`; `/home/forge/dev/repos/commerce-architect/backend/catalog/portability/schema.py`; `/home/forge/dev/repos/commerce-architect/backend/tests/fixtures/catalog_portability/`; `/home/forge/dev/repos/commerce-architect/backend/tests/test_catalog_portability_schema.py`.
- **Data/migration:** none. Define field names, enums, error codes, limits, and entity/schema version constants.
- **Logic/interface/security:** pure schema contracts; no interface; no dynamic code/schema loading.
- **Tests:** minimal empty catalog; one Product with no image; two Products sharing one image binary; active/inactive mixed fixture; exact field/type/range boundaries; unknown field/version/features; float/boolean-as-integer rejection.
- **Acceptance:** valid/invalid fixture inventory has explicit expected outcomes and maps to sections 2, 3, and 6; no transport depends on ORM field introspection.
- **Dependencies:** accepted design and applicable section 9 decisions.
- **Do not:** implement import, expand schema, or treat unfinished foundation fields as optional.

### T02 — Add the Organization catalog foundation

- **Objective:** introduce the already specified Organization ownership boundary without building membership or tenant-routing systems.
- **Files:** `/home/forge/dev/repos/commerce-architect/backend/organizations/models.py`, `__init__.py`, `apps.py`, `admin.py`, and `migrations/0001_initial.py` in that same directory; `/home/forge/dev/repos/commerce-architect/backend/config/settings.py`; `/home/forge/dev/repos/commerce-architect/backend/tests/test_organization_model.py`.
- **Data/migration:** Organization with immutable local PK, required name (255 characters), `status` active/inactive, created_at, updated_at; initial migration; no automatic seed Organization.
- **Logic/interface/security:** no interface; admin restricted to active superusers; add explicit storefront Organization setting and portability enable setting, both without implicit Organization selection. Public routing activation comes in T06.
- **Tests:** required nonblank name; allowed status values; no seed data after migration; non-superuser admin denied; missing configuration cannot select an arbitrary Organization.
- **Acceptance:** domain boundary exists and tests prove explicit selection.
- **Dependencies:** T01.
- **Do not:** add membership, Customer relationships, capability engines, or import Organizations from packages.

### T03 — Prepare Product fields and persistent identity

- **Objective:** add fields without inventing business values for existing data.
- **Files:** existing `/home/forge/dev/repos/commerce-architect/backend/catalog/models.py`; new `/home/forge/dev/repos/commerce-architect/backend/catalog/migrations/0002_prepare_catalog_portability.py`; `/home/forge/dev/repos/commerce-architect/backend/tests/test_catalog_identity_migration.py`.
- **Data/migration:** nullable Organization FK with PROTECT, nullable SKU and stock for transitional existing rows, portable UUID, updated_at. Add UUID nullable first, generate one distinct UUIDv4 per existing Product, then enforce UUID non-null. Preserve Product PKs, price precision, product_type, created_at, and is_active. Initialize updated_at from created_at for existing rows.
- **Logic/interface/security:** new Product creation requires valid owner/SKU/stock via shared validation; UUID not editable in normal admin; no interface.
- **Tests:** migrate multiple legacy rows; distinct stable UUIDs; rerunning migration state does not regenerate IDs; original fields/PKs unchanged; normal creates receive UUIDs; supplied malformed UUID rejected.
- **Acceptance:** old data remains readable and no arbitrary Organization/SKU/stock has been assigned; portability remains disabled on incomplete catalogs.
- **Dependencies:** T02.
- **Do not:** use one pre-evaluated UUID default for all migrated rows or derive UUIDs from database PKs.

### T04 — Bootstrap existing catalog and enforce final constraints

- **Objective:** complete the catalog foundation using reviewed installation-specific facts.
- **Files:** `/home/forge/dev/repos/commerce-architect/backend/catalog/management/commands/catalog_bootstrap.py`; `/home/forge/dev/repos/commerce-architect/backend/catalog/bootstrap.py`; `/home/forge/dev/repos/commerce-architect/backend/catalog/migrations/0003_enforce_catalog_foundation.py`; `/home/forge/dev/repos/commerce-architect/backend/tests/test_catalog_bootstrap.py`.
- **Data/migration:** bootstrap map assigns each existing row exactly one Organization, canonical SKU, and stock. This local administrative map may use existing database PKs; it is not the portability format. Final migration asserts completeness, then makes fields non-null and adds `(organization, sku)` and `(organization, portable_id)` uniqueness plus nonnegative price/stock constraints.
- **Logic/interface/security:** `catalog_bootstrap --mapping <file> --validate-only`; apply requires explicit selected Organization and reviewed mapping fingerprint. Entire map validates before one transaction. Require maintenance/exclusive catalog access during this one-time transition. Reject legacy services pending their separate resolution.
- **Tests:** missing/duplicate/unknown row; incomplete owner/SKU/stock; SKU conflict; negative/out-of-range values; active/inactive preservation; apply failure rollback; populated final migration fails on unresolved rows; empty database migration succeeds without seeding.
- **Acceptance:** no data fact is fabricated; all rows conform; migration deployment ordering is documented as prepare → reviewed bootstrap → enforce, with writes stopped during transition.
- **Dependencies:** T03 and reviewed legacy-data decisions.
- **Do not:** create Orders, convert services automatically, or merge rows by name/SKU.

### T05 — Implement ProductImage and its constraints

- **Objective:** model the specified image aggregate independently of storage implementation.
- **Files:** `/home/forge/dev/repos/commerce-architect/backend/catalog/models.py`; `/home/forge/dev/repos/commerce-architect/backend/catalog/migrations/0004_product_image.py`; `/home/forge/dev/repos/commerce-architect/backend/catalog/admin.py`; `/home/forge/dev/repos/commerce-architect/backend/tests/test_product_image_model.py`.
- **Data/migration:** Product FK; persisted portable UUID; storage_key (max 512); alt_text (max 2,000); nonnegative sort_order; is_primary; created_at/updated_at. Add unique `(product, portable_id)` and conditional unique Product where is_primary is true; restrict explicit image reparenting. Product→image cascade is permitted only inside the protected purge flow.
- **Logic/interface/security:** aggregate validation and primary switch inside a transaction, clearing old primary before setting the new one; no interface; superuser-only admin; no public raw storage keys.
- **Tests:** zero images; zero primary; second primary rejected by DB; primary switch succeeds; tie ordering by UUID; duplicate image identity rejected; same UUID under different parent valid; negative sort invalid; reparent denied.
- **Acceptance:** field and database invariants hold independently of importer behavior.
- **Dependencies:** T04.
- **Do not:** use image1/image2 columns, accept URL fetching, or assume container-local media.

### T06 — Enforce scoped reads and the catalog write lock

- **Objective:** make the ownership/concurrency protocol true for every existing catalog entry point.
- **Files:** `/home/forge/dev/repos/commerce-architect/backend/catalog/services.py`; `/home/forge/dev/repos/commerce-architect/backend/catalog/admin.py`; `/home/forge/dev/repos/commerce-architect/backend/catalog/views.py`; `/home/forge/dev/repos/commerce-architect/backend/catalog/serializers.py`; `/home/forge/dev/repos/commerce-architect/backend/tests/test_catalog_scope_and_locking.py`; existing `/home/forge/dev/repos/commerce-architect/backend/tests/test_product_api.py`.
- **Data/migration:** none.
- **Logic/interface/security:** shared Organization-first lock with five-second timeout; admin create/edit/image/activation paths use it; disable ordinary Product hard-delete/bulk-delete admin paths. GET `/api/products/` uses configured active Organization, active physical Products, deterministic portable-ID order. Preserve existing API fields; image metadata/URLs become available after T08. Reject arbitrary client Organization selection; fail closed if configuration invalid.
- **Tests:** A/B isolation; public unauthenticated list; inactive Organization/products excluded; no cross-Organization query override; staff admin denied; PK/UUID ownership immutable; concurrent admin/import-like writer serialization including zero initial rows; lock timeout reported without mutation. Use independent PostgreSQL connections and transaction-enabled tests, not SQLite.
- **Acceptance:** enumerate every existing writer in review; none bypasses the shared protocol. Bootstrap after foundation uses the same protocol where applicable.
- **Dependencies:** T05.
- **Do not:** change authentication/account architecture, add multi-tenant host routing, or claim a row lock protects nonparticipating writers.

### T07 — Implement pure canonical codec and safe archive reader

- **Objective:** encode deterministic packages and decode bounded untrusted archives without database/storage access.
- **Files:** `/home/forge/dev/repos/commerce-architect/backend/catalog/portability/codec.py`, `archive.py`, `errors.py`; `/home/forge/dev/repos/commerce-architect/backend/tests/test_catalog_package_codec.py`; `/home/forge/dev/repos/commerce-architect/backend/tests/test_catalog_archive_security.py`.
- **Data/migration/interface:** none.
- **Logic/security:** exact section 2 serialization; section 6 limits/path grammar; streamed hashes/sizes; strict JSON; no archive extraction API. Use private staging abstractions with deterministic cleanup.
- **Tests:** byte-identical exports across time/order fixtures; ZIP golden header fixture; every malformed/unknown/duplicate JSON case; UUID/SKU duplicates; broken references/counts/hashes; missing/extra members; traversal variants, symlinks, duplicate/case-alias paths, compressed/encrypted/ZIP64 archives; actual bytes beyond advertised limits; max boundary and one over each limit.
- **Acceptance:** valid fixtures round-trip; malformed fixtures fail with stable codes and zero DB/media calls; temporary resources cleaned after failure.
- **Dependencies:** T01; can be coded before T02–T06 once schema is accepted.
- **Do not:** use dumpdata, pickle, ORM serializers, automatic JSON coercion, or repair invalid input.

### T08 — Implement image verification and immutable media adapter

- **Objective:** verify original image bytes and store them durably before catalog references exist.
- **Files:** `/home/forge/dev/repos/commerce-architect/backend/catalog/media.py`; `/home/forge/dev/repos/commerce-architect/backend/catalog/portability/images.py`; `/home/forge/dev/repos/commerce-architect/backend/config/settings.py`; `/home/forge/dev/repos/commerce-architect/backend/requirements.in` and `requirements.txt`; `/home/forge/dev/repos/commerce-architect/backend/tests/test_catalog_media.py`.
- **Data/migration:** no DB changes. Destination keys are generated by the adapter within a configured catalog namespace using content hash and verified suffix; source keys/URLs never cross the package boundary. Native/admin image writes also use this adapter; they cannot save arbitrary unverified storage keys or overwrite existing bytes.
- **Logic/interface/security:** verify MIME, dimensions, pixel budget, single frame, full decoding; read/write/verify immutable objects and obtain display URLs. Adapter must preserve exact keys or fail, never accept storage-generated alternate filenames; reuse only matching bytes. Persistent local adapter for development/tests; wire approved durable backend through configuration. No interface.
- **Tests:** valid JPEG/PNG/WebP; corrupt/truncated/animated/SVG/disguised files; oversized dimensions/pixels/bytes; equal bytes deduplicate; mismatched existing object fails; interrupted write cannot be referenced; concurrent identical writes resolve to valid immutable object; production rejects unapproved ephemeral fallback; signed URL/storage key never serialized.
- **Acceptance:** adapter conformance proves write completion/read integrity and exact-byte retrieval; decoder dependency locked; no provisioned cloud resources in this packet.
- **Dependencies:** T05, T07, approved production storage choice for its backend-specific wiring.
- **Do not:** transform image bytes, use source URLs, delete shared objects, or promise durability from ephemeral paths.

### T09 — Implement consistent full export

- **Objective:** export one complete current Organization catalog with exact image bytes.
- **Files:** `/home/forge/dev/repos/commerce-architect/backend/catalog/portability/exporter.py`; `/home/forge/dev/repos/commerce-architect/backend/tests/test_catalog_export.py`.
- **Data/migration/interface:** none.
- **Logic/security:** under the Organization lock capture complete Product/image records and immutable media references; release lock after snapshot capture, then read immutable media and build ZIP. Reject unsupported/incomplete entities and missing/corrupt media. Export selected Organization only; atomically publish a completed 0600 output without overwriting existing destination.
- **Tests:** active and inactive completeness; zero records; shared binaries; missing media produces no final artifact; concurrent writer results in a coherent before-or-after snapshot; identical state in different PK layouts yields same bytes; existing output file unchanged on failure.
- **Acceptance:** counts/hashes correct; canonical full package passes T07/T08 validation; no source storage metadata leaks.
- **Dependencies:** T06–T08.
- **Do not:** assign portable IDs during export or silently exclude unrepresentable entities.

### T10 — Implement pure target reconciliation and preview

- **Objective:** calculate the exact mode/stock-dependent action plan without mutations.
- **Files:** `/home/forge/dev/repos/commerce-architect/backend/catalog/portability/planner.py`; `/home/forge/dev/repos/commerce-architect/backend/catalog/portability/compatibility.py`; `/home/forge/dev/repos/commerce-architect/backend/tests/test_catalog_import_plan.py`.
- **Data/migration/interface:** none.
- **Logic/security:** plan from validated package plus target snapshot; compute stable target digest; enforce every section 3 conflict rule; ordered bounded errors; fail if target contains unsupported types/extensions. Match scoped identities only.
- **Tests:** create/update/no-op; safe SKU change; conflicting inactive SKU; SKU swaps rejected; duplicate IDs; authoritative empty/nonempty image sets; merge absent untouched; replace absent deactivated; both stock policies; empty package; A/B same SKU/UUID isolation; stable digest/order/errors; an undeclared field, relation, or inventory integration blocks compatibility rather than being silently ignored.
- **Acceptance:** each fixture has exact action counts/identities/effective values; validation performs zero writes to DB or durable storage.
- **Dependencies:** T06–T08.
- **Do not:** add force/fuzzy matching, hidden defaults, implicit identity changes, or reuse a preview as an authorization token.

### T11 — Add durable operation receipts

- **Objective:** resolve successful retries and uncertain commit acknowledgements without repeating mutations.
- **Files:** `/home/forge/dev/repos/commerce-architect/backend/catalog/models.py`; `/home/forge/dev/repos/commerce-architect/backend/catalog/migrations/0005_catalog_operation_receipt.py`; `/home/forge/dev/repos/commerce-architect/backend/catalog/portability/receipts.py`; `/home/forge/dev/repos/commerce-architect/backend/tests/test_catalog_operation_receipts.py`.
- **Data/migration:** immutable receipt with unique UUID operation ID; protected Organization FK; operation type; nullable package hash; inventory policy where applicable; expected/pre- and post-catalog digests; exact confirmation/input fingerprint; result counts JSON; completion time. No package bytes or credentials.
- **Logic/interface/security:** compare semantic input fingerprint; return prior receipt only on exact match; no interface; receipts internal to trusted operator services and not publicly serialized.
- **Tests:** exact retry returns prior result; changed mode/package/target/policy/precondition fails; concurrent ID uniqueness; transaction rollback leaves no receipt; receipt survives catalog purge; completion time immutable.
- **Acceptance:** idempotency semantics are independent of current catalog state after a completed operation.
- **Dependencies:** T04, T10.
- **Do not:** create a receipt for validate-only or label failed/unknown work successful.

### T12 — Implement atomic import application

- **Objective:** apply the verified plan and all database changes as one commitment.
- **Files:** `/home/forge/dev/repos/commerce-architect/backend/catalog/portability/importer.py`; `/home/forge/dev/repos/commerce-architect/backend/tests/test_catalog_import_transactions.py`.
- **Data/migration/interface:** none.
- **Logic/security:** implement section 3 staging, receipt retry, Organization lock, under-lock digest/precondition checks, scoped aggregate updates, image removals/primary switches, replace deactivation, and receipt transaction. Apply stock guard in service as well as future command layer. Read from the verified immutable package copy.
- **Tests:** inject failure after Product create/update, image replacement/removal, primary clearing, replace deactivation, and receipt creation; assert full rollback. Object-write failure yields zero DB mutation. Stale digest/package fails. Two concurrent imports/duplicate operation IDs behave as specified. Retry after simulated lost response returns receipt. Second import of unchanged state preserves timestamps.
- **Acceptance:** all sections 3 and 5 import invariants pass on PostgreSQL; existing primary keys retained; immutable orphan media permitted but never broken committed references.
- **Dependencies:** T08, T10, T11; architecture review before coding this packet.
- **Do not:** catch-and-continue per row, commit partial batches, promote required images after commit, or delete media on rollback.

### T13 — Implement production-safe storefront reset

- **Objective:** make selected Product storefront empty while preserving all retained catalog/history data.
- **Files:** `/home/forge/dev/repos/commerce-architect/backend/catalog/portability/reset.py`; `/home/forge/dev/repos/commerce-architect/backend/tests/test_catalog_storefront_reset.py`.
- **Data/migration/interface:** none.
- **Logic/security:** shared preview digest/lock, explicit Organization confirmation, all-active-to-inactive update, local updated_at only on changed rows, transaction receipt; internal validate-only path.
- **Tests:** zero visible target Products; all other fields/images/PKs unchanged; B untouched; empty reset idempotent; stale preview fails; injected failure rolls back; repeated operation ID returns original receipt.
- **Acceptance:** no Product/image DELETE and no stock write is issued; reset works under production settings.
- **Dependencies:** T06, T10–T12.
- **Do not:** clear carts, alter Orders, remove media, or couple safe reset to development flags.

### T14 — Expose trusted-operator commands and confirmations

- **Objective:** provide one explicit, documented operational surface around tested services.
- **Files:** `/home/forge/dev/repos/commerce-architect/backend/catalog/management/commands/catalog_export.py`, `catalog_validate.py`, `catalog_import.py`, `catalog_reset_storefront.py`, and `catalog_operation_status.py`; `/home/forge/dev/repos/commerce-architect/backend/tests/test_catalog_commands.py`; `/home/forge/dev/repos/commerce-architect/.env.example`.
- **Data/migration:** none.
- **Interfaces:** export requires `--organization` and `--output`; validate requires `--organization`, `--input`, `--mode merge|replace-storefront`, with `--inventory preserve|restore-snapshot` default preserve. Import requires the same plus `--operation-id`, `--expected-catalog-digest`, `--confirm-package-sha256`; replace additionally requires `--confirm-organization`. Reset requires Organization and supports `--validate-only`; apply also requires operation ID, expected digest, and Organization confirmation. Operation status requires Organization and operation ID.
- **Logic/security:** feature enable guard; explicit missing-argument errors; bounded JSON reports; success exit 0, invalid package 2, target conflict/stale 3, forbidden configuration/policy 4, I/O/transaction/unknown outcome 5. No HTTP routes; no fake `--user` authentication. Status reads successful receipt or reports unknown/not recorded without implying rollback.
- **Tests:** exact parser/flag requirements; production export/validate/merge/replace/reset allowed; production snapshot restore rejected even with flag/DEBUG; mismatched confirmations fail; output permission/no-overwrite; no import/reset API route; regular JWT cannot reach internal services through any route; invalid Organization cannot default to another.
- **Acceptance:** commands delegate to service invariants; command input alone cannot bypass them; no destructive action follows validate-only.
- **Dependencies:** T09, T12, T13.
- **Do not:** add browser UI, background queues, or shell command execution from package contents.

### T15 — Add isolated development purge

- **Objective:** support safe-to-run destructive catalog cleanup only when no external records reference the deletion set.
- **Files:** `/home/forge/dev/repos/commerce-architect/backend/catalog/portability/dev_reset.py`; `/home/forge/dev/repos/commerce-architect/backend/catalog/management/commands/catalog_dev_purge.py`; `/home/forge/dev/repos/commerce-architect/backend/tests/test_catalog_dev_purge.py`; existing settings and `.env.example`.
- **Data/migration:** none; use receipt table, retaining it on purge.
- **Logic/interface/security:** all section 4 guards, `--validate-only` preview, explicit Organization, digest, operation ID, literal purge confirmation; allowlisted internal deletion graph; reject known and unknown external references; same lock and transaction. Inspection must include registered generic/external reference checks and fail closed on unsupported extensions.
- **Tests:** production denied with every override; development without flag denied; confirmation mismatch; A purge/B preserved; external FK with CASCADE still blocks; PROTECT reference blocks; generic/unknown reference compatibility blocks; injected deletion failure rolls back; receipts/media retained; no sequence reset.
- **Acceptance:** only unreferenced Product/image rows are deleted and no other database table is mutated except the new receipt.
- **Dependencies:** T06, T11, T13, T14; architecture review of deletion allowlist before coding.
- **Do not:** add `--force`, delete Orders/Carts/accounts, use flush, or call database drop/truncate.

### T16 — Complete storefront image presentation

- **Objective:** make the specified Product image order and primary behavior visible without a portability UI.
- **Files:** `/home/forge/dev/repos/commerce-architect/backend/catalog/serializers.py`; `/home/forge/dev/repos/commerce-architect/frontend/src/types/product.ts`; `/home/forge/dev/repos/commerce-architect/frontend/src/components/ProductCard.tsx`; existing component/API tests; `/home/forge/dev/repos/commerce-architect/backend/tests/test_product_image_api.py`.
- **Data/migration/commands:** none; extend existing GET product representation with ordered image metadata and adapter-generated URLs; preserve existing Product fields.
- **Logic/security:** show primary image or first sorted image; preserve alt text; safe URL generation only from configured adapter; no raw source keys or manifest data. Frontend does no domain/price calculations.
- **Tests:** zero image, explicit primary, no-primary fallback, ties, correct alt text, valid URL shape; inactive/cross-Organization image data not exposed; reset empty-state UI; same portable metadata gives same selected image after restore.
- **Acceptance:** existing catalog UI remains compatible and images use domain ordering. Manual rendering checks required for visual equivalence claims.
- **Dependencies:** T06, T08.
- **Do not:** redesign the storefront, add image editing/optimization, or implement unrelated cart/checkout work.

### T17 — Prove round trips, security, history boundaries, and delivery

- **Objective:** establish release evidence for all invariants and document exact operator procedures.
- **Files:** `/home/forge/dev/repos/commerce-architect/backend/tests/test_catalog_portability_roundtrip.py`; `/home/forge/dev/repos/commerce-architect/backend/tests/test_catalog_history_boundary.py`; `/home/forge/dev/repos/commerce-architect/docs/CATALOG_PORTABILITY.md`; `/home/forge/dev/repos/commerce-architect/backend/README.md`; existing CI workflow only if a required check is missing.
- **Data/migration/interface:** none.
- **Logic/security:** test-only reference fixtures may exercise external FK protection without adding production Order models. Mark real future Orders/checkout integration tests as explicit enablement requirements; do not claim they ran against nonexistent domains.
- **Tests:** soft-reset→replace restore; development purge→fresh restore with different PKs; fresh Organization canonical ZIP equality; merge preserves destination-only Products; replace retains inactive extras; production preserves stock; two-Organization same UUID/SKU; full hostile package matrix; independent-connection race tests; all durable fixture fields/references unchanged; operation retry after simulated lost acknowledgement.
- **Acceptance:** backend pytest with PostgreSQL, Django checks, migration drift check, migration tests from populated prior schema, existing CI image checks, and frontend tests/lint/build for T16 all pass. Manual UAT records export/reset/restore in disposable development, expected empty/storefront/image behavior, and production-policy denial. Report according to `/home/forge/dev/repos/commerce-architect/docs/VALIDATION_STANDARDS.md`. Confirm durable production storage adapter conformance before enabling images in that environment.
- **Dependencies:** T01–T16; final architecture/security review before enabling feature.
- **Do not:** run destructive UAT against production, claim real Orders protection from mocks alone, or change deployment credentials/services as part of this task.

## 11. Suggested execution order and reasoning allocation

First, one higher-reasoning review accepts this contract and resolves the actual legacy-data/media decisions. This is essential because those facts are absent from the checkout; Luna should not discover them by guessing.

Then execute T01 → T02 → T03 → T04 → T05 → T06 → T07 → T08 → T09 → T10 → T11. T07 can be done earlier after T01, and T16 can follow T08; these are dependency options, not requests to start parallel agents.

Perform one focused higher-reasoning review before T12, covering the target lock protocol, stock policy, image readiness/orphan handling, receipt idempotency, and error paths. Luna Medium can then implement T12 → T13 → T14. Review T15's deletion allowlist and future-reference stop conditions before Luna implements it. Complete T16 and T17.

Luna Medium can implement every accepted work packet. Reserve expensive reasoning for acceptance of the contract, the T12 transaction/concurrency review, the T15 destructive-boundary review, and final conformance review. Routine model/codec/command/frontend/test work does not require repeated architectural exploration. A failing invariant returns the implementation to its owning packet; it does not authorize relaxing the contract.

The migration transition T03→T04 is a deployment sequencing gate, not a normal unattended “run all migrations over unknown data” step. Keep writes paused during the one-time bootstrap. New empty installations need no fabricated seed data and can complete the schema migrations normally.

When Orders/checkout are later implemented, their release must add real integration tests that place an Order, capture all durable records, run merge/replace/soft reset, and prove every historical snapshot/reference unchanged. Their inventory writers must join the common lock/protection contract, and purge must reject their references. That future requirement does not authorize building those domains in this implementation.

## 12. Final implementation contract for Luna Medium

Implement Catalog Portability as Organization-scoped domain services in the existing Django catalog app, with trusted-operator management commands. Follow this accepted specification and authoritative Product Commerce documents. No implementation is authorized until the user requests it.

**V1 includes:** required Organization/Product/ProductImage catalog foundations; stable scoped UUID transport identity; complete deterministic ZIP packages of active and inactive physical Products and embedded images; strict bounded validation; merge and replace-storefront; safe soft reset; guarded development purge and snapshot stock restore; default preservation of live stock; immutable media readiness before database commit; successful operation receipts; and PostgreSQL conformance tests.

**V1 excludes:** database backups, ORM fixtures, Organization/history/account transfer, Orders/checkout/payment implementation, browser operator UI, automatic conflict repair, partial import, production snapshot-stock overwrite, generalized migrations/plugins, advanced catalog/inventory, and media garbage collection.

**Never violate:** explicit Organization isolation; UUID independence from primary keys; scoped SKU uniqueness; zero mutation during validate-only; all-or-nothing catalog database changes; no committed broken media references; no Product hard-delete in production operations; unchanged durable commerce history; explicit stock policy; no production development-reset bypass; deterministic bytes; idempotent receipt-based retries; and rejection of unsupported data rather than silent omission.

**Expected final behavior:** an operator exports a complete catalog, previews and soft-resets its storefront to empty, previews and imports the same package with replace-storefront, and restores its active Product set, descriptive fields, identities, and image presentation without recreating existing Product rows or changing historical records. A compatible empty development target can reproduce all portable content and stock using explicitly permitted snapshot restore. Production import preserves existing stock and starts newly imported Products at zero stock.

**Ordered packets:** T01 schema/fixtures → T02 Organization → T03 Product preparation/UUID backfill → T04 reviewed bootstrap/final constraints → T05 ProductImage → T06 scope/write locking → T07 canonical codec/safe archive → T08 verified immutable media → T09 full export → T10 preview/reconciliation → T11 operation receipts → reviewed T12 atomic import → T13 soft reset → T14 commands → reviewed T15 development purge → T16 image presentation → T17 conformance/UAT/docs and final review.

If existing data mapping, service classification, required storage configuration, or a new domain extension is unresolved, stop only the affected dependent packet and state the exact unmet precondition. Do not invent data, bypass a guard, add a force option, silently omit fields/entities, or broaden the feature to solve unrelated architecture.
