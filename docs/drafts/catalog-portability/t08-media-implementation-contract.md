# T08 — verified immutable media: tightened implementation contract

Review date: 2026-09-09. Baseline inspected: `68227f43ad5dd193a6624ad1c39ff9610880fe21`, including merged T01–T07. Status: architecture contract for implementation when requested; this review does not implement T08, provision infrastructure, or start T09.

**Verdict: the accepted T08 design remains sound with R2.** Implement a small S3-compatible storage adapter configured for R2, a persistent local adapter, a separate delivery URL policy, and Product-image verification in the catalog service. Deliver actual bucket/domain configuration as **T08-H, an immediately adjacent Hosting step that gates T08 completion**. No R2 details belong in ProductImage.

## Review findings and changes to the accepted packet

| Priority | Finding | Required resolution |
|---|---|---|
| High | “Immutable write” was underspecified for concurrent writers and uncertain upload outcomes. | Atomic create-if-absent, origin readback, byte verification, bounded conditional retries, and no overwrite/rename fallback. |
| High | Private storage/write access could be mistaken for private image delivery. | Ordinary catalog image bytes are public through the configured custom hostname; authenticated origin access controls application reads/writes. No presigned storefront GETs. |
| High | Existing admin permits arbitrary `storage_key` entry; T07 hash checking does not decode images or establish that the hash embedded in a media filename equals the actual digest. | Make raw keys read-only/disable raw-key creation; require the T08 image boundary to verify bytes, filename digest, descriptor, type, and limits before storage. |
| Medium | Original T08 expressly deferred cloud provisioning. | Supersede that delivery boundary with required T08-H in the same window; keep provisioning outside application code. |
| Medium | Cached 404s can outlive a newly created origin object. | Validate durability through authenticated origin reads; configure media delivery to avoid negative caching and verify the custom domain independently. |
| Medium | Local persistence and media URL generation have no current configuration. | Add an explicit persistent local volume, development-only serving, and independently configured public delivery origin. Never use WhiteNoise for mutable media. |

The original packet's image limits, exact-byte preservation, provider neutrality, no DB schema changes, and retention of orphan objects remain in force. This contract tightens durable key syntax to an extension-free SHA-256 key; the frozen package's `media/<hash>.<extension>` syntax remains unchanged. It replaces only T08-specific ambiguities, not the T01 schema or later import contract.

Read sources: [original full design](/tmp/catalog-portability-design/catalog-portability-v1.md), [repository schema](/home/forge/dev/repos/commerce-architect/docs/CATALOG_PORTABILITY.md), [architecture](/home/forge/dev/repos/commerce-architect/docs/ARCHITECTURE.md), [build/deployment contract](/home/forge/dev/repos/commerce-architect/docs/BUILD_DEPLOY.md), [testing strategy](/home/forge/dev/repos/commerce-architect/docs/TESTING_STRATEGY.md), [validation standards](/home/forge/dev/repos/commerce-architect/docs/VALIDATION_STANDARDS.md), and applicable onboarding, Docker, platform philosophy, security, UX, contribution, and feature/review guidance. Inspected models, admin, locking services, serializers, T07 codec/reader/schema, tests, settings, Docker/Compose, and CI configuration. The repository portability document still describes T01; it must not be interpreted as proof that T07 decodes or stores images.

## 1. Objective

Establish a tested media boundary that validates supported Product images, stores their original bytes immutably, retrieves and verifies them, and generates stable public delivery URLs independent of storage-provider addresses. Supply persistent local development behavior and a working production R2/custom-domain deployment within the T08 delivery window.

T08 creates no exporter/importer, no catalog reset, no new catalog upload API, and no storefront rendering change. T09 and T16 consume this boundary later.

## 2. Accepted human decisions

- Production: Cloudflare R2, **Standard**, explicit **`us` jurisdiction**.
- Preferred production delivery origin: **`https://media.empowerment-forge.com`**. Treat availability/ownership as a Hosting preflight fact, not something this review has verified.
- Private credential-controlled storage/write boundary plus controlled public read delivery through the custom Cloudflare/R2 hostname.
- Disable `r2.dev`. No public writes. No presigned GET dependency for ordinary storefront images.
- SHA-256 content addressing; existing content must never be replaced with different bytes.
- Local development: persistent filesystem through the same storage contract. Tests may inject an in-memory implementation.
- Provider-neutral models/services; storage and delivery implementation/configuration are replaceable.
- Future audio/video/download/transcoding/live-provider capabilities are possible extensions, not T08 implementations.

Cloudflare currently documents `us` as a supported jurisdiction and requires the jurisdiction-specific S3 endpoint. A location hint such as `enam` is not an equivalent residency restriction; jurisdiction is fixed at bucket creation. This contract applies US jurisdiction to R2 storage/processing and does not claim US-only browser delivery or worldwide CDN cache placement. [R2 data location](https://developers.cloudflare.com/r2/reference/data-location/)

## 3. Architecture boundary

| Layer | Responsibilities | Forbidden coupling |
|---|---|---|
| Catalog image service | Product-image policy, decoder checks, package expectations, conversion between package path and durable reference | R2 endpoints, credentials, bucket creation, CDN administration |
| MediaStorageAdapter | Exact-byte create-if-absent and verified origin retrieval | Product IDs, Organization lookups, Django models, image decoding, public URL generation |
| MediaDelivery policy | Deterministic public URL from configured origin and validated key | Uploading, existence probes, SDK signing, DB mutation |
| ProductImage | Existing parent/portable identity, opaque storage key, alt text, order, primary selection, timestamps | Bucket/provider hostname, presigned URL, provider credentials, SDK objects |
| Hosting T08-H | Buckets, jurisdiction/class, access, domains/TLS/cache/headers, runtime secret/configuration delivery | Domain schema changes, provisioning in model save or application startup |

Create a plain Python `backend/media_storage/` package, not a Django app or new Media database entity. Keep Product-specific rules in `backend/catalog/media.py` and `backend/catalog/portability/images.py`. Reuse existing `catalog_write_lock` for any catalog DB mutation; do not hold that lock while decoding or uploading.

SHA-256 identifies binary content. ProductImage.portable_id identifies the catalog image relationship. Different image rows may reference the same bytes while retaining distinct alt text/order/primary state. Storage deduplication never merges ProductImage rows or changes their UUIDs.

No database migration is required. Leave existing ProductImage FK protection, primary constraints, reparenting protection, and portable identity unchanged.

## 4. Media adapter contract

Expose exactly two storage operations. These are interface specifications, not implementation code:

| Operation | Inputs | Return and guarantee |
|---|---|---|
| `put_if_absent` | Immutable `bytes` plus an exact canonical content-type string from the media service | A `StoredMedia` value, only after complete durable origin readback verifies exact bytes, hash, length, and required content metadata. Computes the key itself; caller cannot choose a destination path. Reuses identical existing bytes without changing them. |
| `read_verified` | Validated storage key and positive `max_bytes` bound | A `StoredMediaBytes` value containing original bytes and verified descriptor, or a typed error. Fully consumes a bounded authenticated origin read, hashes it, and checks the digest encoded in the key. |

`StoredMedia` contains exactly storage_key, sha256, size_bytes, content_type. `StoredMediaBytes` adds immutable bytes. No ETag, bucket, provider URL, SDK response, signed URL, model instance, or “created” claim belongs in the contract. A timed-out upload followed by successful readback may not establish which attempt created the object; only verified readiness matters.

Use bytes in T08 because accepted images are at most 10 MiB and T07 already supplies bytes. Do not introduce a large-media streaming subsystem now. Future large-media ingress can add a bounded-stream operation without changing ProductImage or putting image policy into the adapter.

Image-service functions:

- `verify_product_image`: bytes plus optional package expectations → prepared image descriptor/bytes, width, height, and canonical extension; zero DB/storage mutation.
- `verify_package_images`: a decoded T07 CatalogPackage → a validated mapping for all distinct assets; complete verification of every asset before any caller starts durable writes. Zero durable writes itself.
- `store_verified_product_image`: prepared bytes → StoredMedia through the selected adapter; recheck byte digest/length at the boundary; no DB mutation.
- `read_product_image`: storage_key → verified, decoded Product image and descriptor using origin reads; useful to T09 later, but do not implement T09.

The separate `MediaDelivery.public_url` accepts only a validated storage_key and returns a URL without network or DB access. Its instance is specifically configured for this public-image corpus; it is not a universal access policy for all future media.

Do not expose `save`, `overwrite`, `rename`, `delete`, `list`, presign, bucket-management, or a success-returning `exists` shortcut on MediaStorageAdapter. Avoid default Django storage `save()` behavior that can choose an alternate filename. No dynamically imported provider path controlled by uploaded data.

## 5. Content-addressing rules

The exact durable key is **`sha256/<64-lowercase-hex-digest>`**, calculated over all original file bytes. No suffix, source filename, Product/Organization ID, timestamp, or provider component. Its 71 ASCII characters fit the existing storage_key column. Both adapters use the same logical key.

The package path remains **`media/<same-digest>.<jpg|png|webp>`**, with extension determined by verified image format. These namespaces intentionally differ. T08 provides explicit conversion after verification; never persist package asset_path verbatim or mistake it for an arbitrary local file path.

Checksums on metadata and S3 ETags are not authoritative content identity. Hash actual bytes on ingress and retrieval. On duplicate writes, compare exact retrieved bytes with the attempted content as well as hash/length. If content differs at a claimed existing key, fail and leave it untouched—even if a test simulates a hash collision.

Deduplicate across Products/Organizations within the same configured public-image store. Production and hosted development use different buckets and credentials; no deduplication attempt crosses environments. Referencing the same public bytes does not authorize changes to another Organization's ProductImage metadata.

Existing bytes with mismatched MIME or required delivery metadata are an integrity/configuration failure. Do not “repair” by overwriting metadata at that key. An authorized incident procedure may diagnose the object later; T08 never substitutes a new key to hide the failure.

## 6. Image validation rules

Reuse versioned limits from `catalog.portability.schema`, rather than copying independent values: 10 MiB encoded bytes, 40,000,000 pixels, maximum width/height 12,000, and positive dimensions. Lower local limits are permitted; raising v1 limits is not. Reject zero-length content. Each decoder operates on one image at a time; do not decode all package images concurrently.

For every image, before durable storage:

1. Enforce actual input byte limit and copy mutable input to immutable bytes; never reopen a user-selected source path after verification.
2. Compute SHA-256 and actual length. For package content, require equality with manifest digest, manifest length, digest in asset_path, and the referenced asset bytes. A manifest that agrees with bytes while the filename contains a different digest is invalid.
3. Open with Pillow restricted to JPEG, PNG, and WebP. Determine actual format from decoding, not filename or client Content-Type.
4. Require the exact canonical mapping JPEG → image/jpeg → jpg; PNG → image/png → png; WebP → image/webp → webp. In packages, require the descriptor MIME and extension to agree; no `image/jpg`, `.jpeg`, mixed case, or content-type parameters. For native bytes without package metadata, derive MIME/extension rather than requiring a filename. If a caller supplies MIME as an assertion, disagreement is an error.
5. Check dimensions/pixel count before raster allocation. Reject animation or multiple frames, including APNG and animated WebP. Require exactly one frame.
6. Perform Pillow structural verification, reopen the same bytes, and force complete pixel loading. Do not treat a successful lazy open as full validation. Keep truncated-image loading disabled. Treat decompression-bomb warnings/errors as failures. Preserve decoder metadata safety limits; do not disable warnings globally to make fixtures pass. [Pillow Image verification/loading](https://pillow.readthedocs.io/en/stable/reference/Image.html), [truncated-image setting](https://pillow.readthedocs.io/en/stable/reference/ImageFile.html)
7. Return original bytes and independently derived metadata. No resize, re-encode, rotation, EXIF removal, color conversion, thumbnail generation, or compression change.

Reject SVG, HTML, GIF, TIFF, PDF, disguised non-images, truncated/corrupt images, invalid dimensions, and decoder failures. This is bounded image-format validation, not a claim to detect every malicious payload or embedded ancillary byte. Only public catalog images enter this storage service; future private/downloadable media requires its own validation/access policy.

Pin Pillow through the existing requirements.in → generated requirements.txt workflow. Verify JPEG/PNG/WebP decoder availability in the actual production image. Never weaken limits because a decoder/plugin is missing. Pure T07 codec tests can continue using arbitrary bytes to test the transport layer; T08 tests need actual image fixtures and must explicitly reject those arbitrary-byte fixtures as images.

## 7. Storage and delivery separation

ProductImage stores only the relative key. `MEDIA_PUBLIC_BASE_URL` supplies the delivery origin; changing domain or storage provider does not rewrite image rows when keys and bytes are preserved. A provider migration must first copy and verify the entire referenced corpus; changing configuration alone does not transfer data.

`public_url` appends the strictly validated ASCII key to a configured absolute base URL. Reject absolute keys, leading slash, backslash, dot segments, percent-encoded path escapes, query/fragment characters, control characters, and keys outside `sha256/<digest>`. Do not use URL joining that permits a key to replace the host. Production base URL is HTTPS with no userinfo, query, or fragment; this deployment uses a bare custom origin. Local development may use HTTP and a fixed `/media` base path.

Set object Content-Type to the verified MIME, Content-Disposition to inline, and Cache-Control to `public, max-age=31536000, immutable`. No Content-Encoding or image transformations. Hosting adds `X-Content-Type-Options: nosniff` on media responses and forces HTTPS with minimum TLS 1.2.

Extension-free keys require an explicit Cloudflare cache rule for successful `/sha256/` object responses. Cache 200 responses as immutable; do not cache error responses, especially 404. Disable content-changing image optimization on this hostname. Readback for integrity always uses authenticated storage origin, never the CDN. Cloudflare documents both cached-deletion behavior and negative caching independently of origin consistency. [R2 consistency and caching](https://developers.cloudflare.com/r2/reference/consistency/)

All objects in these dedicated buckets are intended for public delivery, including unreferenced objects left after failed DB work. Removing/deactivating a Product or deleting an image association does not revoke a known URL or clear browser/CDN caches. Do not store packages, customer documents, credentials, private downloads, or quarantine content in these buckets. Hashes are not access tokens.

Ordinary HTML image display does not require adding wildcard CORS or sending bearer tokens/cookies. No new application CORS/CSRF policy is needed for this image origin. Canvas, cross-origin JavaScript downloads, and credentialed media access are future scoped requirements. Later T16 must permit the configured image hostname in any relevant CSP without broadening script or connection policies.

## 8. R2 production configuration

### Adapter decision

Implement `S3CompatibleMediaStorageAdapter` using the low-level boto3 client, configured for R2. This is reuse of a documented object-storage protocol and SDK, not adoption of AWS hosting, IAM roles, KMS, S3 website hosting, or AWS-specific domain models. Only claim compatibility for providers passing the exact conditional-write/readback suite. [Cloudflare boto3 example](https://developers.cloudflare.com/r2/examples/aws/boto3/)

Use an explicit endpoint, explicit access key/secret, SigV4, path-style addressing, and region `auto` for R2. Do not use ambient AWS credentials, instance metadata discovery, generated AWS endpoints, or high-level upload helpers that may switch to multipart writes. T08 uses single-request PutObject for each <=10 MiB image.

Required write is PutObject with **If-None-Match: `*`** (`IfNoneMatch` in boto3), exact ContentLength, verified ContentType, inline ContentDisposition, immutable CacheControl, and StorageClass `STANDARD`. R2 documents conditional PutObject and Standard support; its supported subset, not all AWS features, governs the adapter. [R2 S3 compatibility](https://developers.cloudflare.com/r2/api/s3/api/)

Use Content-MD5 for the supported transport integrity check; SHA-256 remains application identity. Explicitly configure SDK request/response optional checksum behavior to `when_required` so an SDK upgrade does not silently introduce unsupported automatic checksum modes. Readback SHA-256/length/byte checks are mandatory regardless of transport checks. Lock boto3 and its resolved botocore dependency using the existing compiler workflow. [Boto3 configuration](https://docs.aws.amazon.com/boto3/latest/guide/configuration.html)

A duplicate conditional write normally fails its precondition; retrieve and verify existing bytes, then return their descriptor. A concurrent conflict or ambiguous network outcome follows section 12. Never fall back to an unconditional PUT, copy-overwrite, alternate filename, or delete/retry.

### Configuration ownership

| Application variable | Contract |
|---|---|
| `MEDIA_STORAGE_BACKEND` | Allowlisted `disabled`, `local`, `s3`; default disabled for staged rollout/build-only contexts |
| `MEDIA_PUBLIC_BASE_URL` | Delivery origin; required when media enabled |
| `MEDIA_LOCAL_ROOT` | Absolute persistent root for local adapter only; not a source-code/static directory |
| `MEDIA_S3_ENDPOINT_URL` | Explicit authenticated storage endpoint; production HTTPS required |
| `MEDIA_S3_BUCKET` | Explicit bucket; required for s3 |
| `MEDIA_S3_REGION` | Explicit signing region; `auto` for R2 |
| `MEDIA_S3_ACCESS_KEY_ID` | Secret configuration, backend only |
| `MEDIA_S3_SECRET_ACCESS_KEY` | Secret configuration, backend only |
| `MEDIA_S3_STORAGE_CLASS` | `STANDARD` for this delivery; no silent class fallback |

Provider-neutral application code has no `R2_ACCOUNT_ID`, Cloudflare zone, or jurisdiction field. The Hosting runbook owns Cloudflare account/zone IDs, bucket names, jurisdiction `us`, and domain binding. It supplies the resulting **`https://<account-id>.us.r2.cloudflarestorage.com`** endpoint via MEDIA_S3_ENDPOINT_URL. Runtime validation checks syntactic safety and explicit settings; Hosting acceptance verifies that the endpoint/bucket actually satisfy the R2 policy. Do not hard-code Cloudflare hostname validation into a generic S3 adapter.

`disabled` makes media operations fail with OPERATION_NOT_ALLOWED; it is not a local-storage fallback. It permits collectstatic/image builds and existing non-media functionality without runtime credentials. T08 acceptance requires s3 enabled in hosted environments. Production must reject local or in-memory adapters. Tests explicitly inject doubles; do not expose a production `memory` backend setting. Leave `CATALOG_PORTABILITY_ENABLED` unchanged; T08 does not enable the unfinished full feature.

Media client creation is lazy. Django startup/collectstatic/system checks validate configuration without network calls, bucket creation, or secret retrieval from a developer's shell profile. Keep existing WhiteNoise static STORAGES configuration independent.

## 9. Local-development configuration

Use a dedicated Compose named volume `catalog_media` mounted at `/var/lib/commerce/media` in the backend, owned by its runtime user. Prepare that directory with UID 10001 ownership in the backend image before switching to its existing non-root user; verify fresh-volume initialization works in both documented Docker and Podman workflows. Do not solve permissions by running the backend as root or granting world-write access. Set MEDIA_STORAGE_BACKEND=local, MEDIA_LOCAL_ROOT to that path, and MEDIA_PUBLIC_BASE_URL=`http://localhost:5173/media` in the container workflow. Ordinary stop/down/recreate preserves the volume. Explicit `down -v` destroys it and must be documented along with existing database volume destruction.

Local storage represents each logical object as a directory containing `content` and a minimal metadata file: exact content_type, sha256, size_bytes. These are storage internals, not domain entities. Never expose either on a browsable filesystem route.

For atomic visibility: use a root-owned adapter namespace and per-key advisory filesystem lock shared across local processes. Write content/metadata into a generated 0700 temporary directory on the same volume, 0600 files, flush/fsync both files and the directory, then rename the complete directory into its final absent key location under that lock; fsync the parent before success. All local reads/writes use the same key lock and reject symlinks/special files. On supported local runtime, the selected advisory-lock mechanism must work across processes. Do not use in-process-only locks or truncate/open an existing content file.

Existing destination is verified and reused, never replaced. Absent/corrupt metadata, wrong content/hash/type, unexpected final directories, or inability to establish the persistence/locking guarantees is MEDIA_UNAVAILABLE. Private temporary directories can be removed by their owning operation; an abandoned one is not a readable final object.

Provide a development-only GET/HEAD route `/media/sha256/<digest>` that reads the adapter's verified object and sends its canonical content type, inline disposition, and nosniff. Add `/media` to Vite's existing backend proxy. No directory listing, raw filesystem path, arbitrary extension, query-selected file, or write route. Register this route only for COMMERCE_ENV=development with local storage; DEBUG alone cannot enable it. Native host developers set the base URL for their chosen development origin.

This small serving route is an infrastructure convenience for local media delivery, not a new catalog upload or operator API. No frontend ProductCard changes in T08.

## 10. Hosting/deployment actions: required adjacent T08-H

Application implementation and Hosting are independently reviewable, but **T08 is not fully delivered until both pass**. The original “no provisioned cloud resources in this packet” applies to application code, not to indefinite deferral of the accepted infrastructure. None of these actions is performed during this review.

Perform the following in the delivery window:

1. **Read-only preflight:** verify the intended Cloudflare account, R2 availability, `empowerment-forge.com` zone ownership in the same account, existing DNS/media host bindings, and the exact hosted backend environments. Do not overwrite an occupied media hostname or reuse an unrelated bucket.
2. **Create isolated buckets:** recommended names `commerce-architect-media-production` and `commerce-architect-media-development`, subject to verified availability. Both use Standard and jurisdiction `us`. Record actual names and read back settings; do not substitute a location hint or a default-jurisdiction bucket. Cloudflare management operations on jurisdictional buckets must carry the required jurisdiction selector/header.
3. **Credential separation:** create bucket-scoped Object Read & Write credentials separately for production and hosted development. Backend credentials must not manage buckets, DNS, custom domains, or account settings. Provisioning credentials stay in operator tooling/secret management, not application runtime. Do not claim provider scope excludes every destructive object operation; conditional application writes, no delete interface, and the bucket protection below establish the intended boundary. [R2 authentication and scopes](https://developers.cloudflare.com/r2/api/tokens/)
4. **Immutability protection:** configure an indefinite bucket-lock rule for prefix `sha256/` as a Hosting guard against accidental overwrite/deletion. Application credentials cannot edit the rule. It complements conditional writes; it does not replace them. An authorized administrator can change the rule, so this is not a claim of compliance-grade tamper-proof retention. Test exact duplicate-read reuse with the lock enabled; a lock-specific refusal is not itself success without authenticated readback. [R2 bucket locks](https://developers.cloudflare.com/r2/buckets/bucket-locks/)
5. **Custom domains:** bind production to `media.empowerment-forge.com`; recommended hosted-development domain `media-dev.empowerment-forge.com` on its separate bucket. Activate TLS and verify provider binding, DNS, and certificate. Use the R2 custom-domain connection, not a CNAME to r2.dev. Disable managed r2.dev access independently on both buckets. Cloudflare supports custom domains independently of r2.dev. [R2 public buckets](https://developers.cloudflare.com/r2/buckets/public-buckets/)
6. **Delivery policy:** enforce HTTPS/minimum TLS, nosniff, canonical Content-Type, no content-transforming optimization, explicit successful-object caching for extension-free keys, and no negative caching. Root requests must not list bucket contents. Normal public GET/HEAD succeeds without app authentication; public PUT/POST/DELETE does not mutate objects. No CORS wildcard or credential forwarding is added.
7. **No automatic disposal:** no lifecycle expiration or class transition on this corpus, no scheduled orphan sweep, no deployment cleanup deleting objects. Keep public catalog-only content segregated from future private assets.
8. **Runtime configuration:** set hosted development and production backend MEDIA_* settings to their distinct s3 buckets/credentials and corresponding public base URLs. Hosted development keeps production security settings. Local Compose uses local storage and never inherits production credentials. Frontend builds receive no write credentials. No credential values appear in commands/logs/docs/PRs; use approved secret inputs.
9. **Deploy through existing release flow:** validate the exact application image in CI without live credentials; deploy to hosted development; run live T08 acceptance; promote the same tested digests through the existing production process. Supply production runtime configuration before its activation. Do not rebuild for promotion, replace Railway deployment credentials, or improvise a separate release path.
10. **Record evidence:** update the established private Hosting runbook with actual bucket/jurisdiction/class, zone/domain bindings, secret ownership (names/scopes only), cache/header/lock settings, deployed digests, and smoke results. Repository docs describe the generic environment contract and local setup. No secret values or adopter-specific identifiers in public domain documentation.

Use harmless, valid image smoke fixtures and retain them as known test assets in the immutable corpus. Any direct raw conditional-write/lock probes that intentionally attempt replacement are restricted to an explicitly selected disposable test object in the development bucket, never an existing catalog object.

## 11. Security requirements

- Only trusted application code can call storage writes; package data cannot select an adapter, endpoint, bucket, secret, or public origin. No network fetching from package image URLs or source metadata.
- Raw `storage_key` becomes read-only in ProductImage admin; disable admin add/raw-content replacement for T08 instead of building a new upload UI. Keep authorized metadata/primary edits and existing scoped deletion behavior. Deleting an association never calls object deletion. Reject forged POST attempts to change keys or parent ownership.
- Provider-neutral model persistence does not perform SDK/network I/O. Supported ingress validates/stores first and passes the returned key into a catalog transaction. Raw ORM/SQL writes by privileged code are not a substitute for that service boundary; preserve T05 model-only tests as such.
- Read-only preflight enumerates any pre-existing noncanonical image keys. Do not silently reinterpret, relocate, or delete them. If present in a target deployment, require an explicit byte-verifiable reconciliation step before enabling T08 there; T08 has no automatic legacy-media migration.
- Local paths must remain inside the configured root; reject symlink traversal even when the key grammar is correct. Local staging is never served. Production cannot activate the local route/backend.
- Direct origin operations verify TLS and use only explicit backend credentials. SDK wire logging is off. Errors expose stable codes and bounded reason text, not authorization headers, secrets, signed requests, response bodies, or filesystem dumps.
- Decoder and SDK dependencies are locked and scanned in the production image; no network install at runtime. Do not disable decoder safety protections to pass a test.

## 12. Failure, retry, and rollback semantics

Use the existing stable ErrorCode enum. Typed media exceptions may carry internal bounded reason identifiers without adding new public package codes:

| Failure | External classification | Required result |
|---|---|---|
| Package descriptor/filename digest disagrees with actual bytes | INVALID_PACKAGE | Reject before durable write |
| Unsupported MIME, multi-frame, corrupt/truncated bytes, decode failure | INVALID_IMAGE | Reject before durable write |
| Byte/dimension/pixel limit or decompression-bomb limit | LIMIT_EXCEEDED | Stop validation; no durable write |
| Malformed external storage key, forbidden local configuration, disabled media | OPERATION_NOT_ALLOWED, or Django configuration error at setup | No I/O through a fallback |
| Missing/corrupt object, metadata mismatch, permissions, endpoint/TLS failure | MEDIA_UNAVAILABLE | No success descriptor; no replacement or deletion |
| Upload response lost or transient provider conflict | Read origin and verify, then bounded conditional retry if needed | Return readiness only when proven |
| DB transaction fails after storage succeeds | Existing catalog error/rollback | Keep durable bytes; do not compensate with deletion |

Successful writes and duplicate reuse both require full authenticated readback. On timeout, connection loss, 409, or precondition failure, attempt origin retrieval. Verified exact bytes/metadata resolve the operation to success. Confirmed NotFound permits retry of the same conditional create; other errors do not mean absent. A lock-specific denial can be resolved by readback of an already existing exact object, but cannot justify retrying an unconditional write. [Conditional PutObject parameter](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/put_object.html)

Set SDK connect timeout 5 seconds, read timeout 30 seconds, and one SDK attempt; the adapter controls at most three conditional write attempts with 100 ms then 500 ms backoff and bounded verification reads. Tests inject the delay function. No unbounded retry and no re-upload under a different key. After exhausted uncertain attempts, raise MEDIA_UNAVAILABLE with internal reason `write_outcome_unknown`; no caller may assume an object is absent or safe to delete.

Database failures, process crashes, and failed future imports may leave unreferenced immutable objects. Keep them. Content-addressed objects may be shared or adopted concurrently; “my upload returned created” is not deletion authority. A later GC design must prove global unreferenced status, coordinate writers, use an age/grace period, and account for CDN/retention policy. No GC code or reference-count deletion is T08 scope.

Local temporary cleanup removes only that operation's generated temporary files/directories while they are not visible final objects. Do not scan/delete other processes' staging directories automatically. Normal tests may tear down their dedicated temporary roots after all workers stop. Production deployment rollback retains buckets, domains, and objects; if image rows reference them, their continued availability is required.

## 13. Required tests

Use exact behavioral assertions, with one reusable adapter conformance suite against in-memory, real local filesystem, and the S3 adapter with controlled SDK responses. Run separate, explicitly marked live R2 tests against the development bucket; PR CI must not receive provider credentials. Emulator/mock success is not evidence of R2 policy, DNS/TLS, US jurisdiction, or CDN behavior.

### Image boundary

- Valid single-frame JPEG/PNG/WebP produce expected MIME, extension, dimensions, byte count, hash, and unchanged bytes.
- Zero-byte, invalid-format, SVG/HTML/GIF/TIFF/PDF, MIME/extension spoof, truncation, corruption, APNG/animated WebP, and oversized metadata/decoder failures are rejected.
- Test each size/dimension/pixel maximum and one above it, with reasonable generated/test fixtures; no unsafe huge allocations.
- Hash in asset_path differs while descriptor hash matches bytes → INVALID_PACKAGE; descriptor size/hash/type mismatch also rejected.
- A package with one valid and one invalid image verifies no durable write for either; repeated binary references verify once and do not create extra blobs.
- Pillow structural verify without full load is not considered success; missing WebP support fails image-build capability check.

### Adapter contract and local concurrency

- Same bytes → same key and descriptor across adapters, time, input filename, Product, and Organization.
- Repeated/concurrent puts → one immutable final object, both callers receive the same verified result.
- Pre-existing corrupt bytes/metadata or simulated hash collision → failure with original object unchanged.
- Mutating the caller's original bytearray cannot change verified/persisted content.
- read_verified enforces actual bytes and max_bytes even when stored metadata lies; incorrect digest/key fails.
- Local two-process concurrent writer/read tests observe complete content plus metadata or absence, never partial final content.
- Fail after temporary content write, metadata write, publish, or fsync: no successful descriptor without verified durable result; existing final objects untouched.
- Symlink roots/components/objects, traversal keys, special files, out-of-root access, and in-process-only locking substitutes fail.
- Recreating the local adapter/backend process with the same persistent root preserves access; directory listing and public local writes fail.

### S3/R2 behavior

- Every new PUT carries IfNoneMatch `*`, correct key/length/type/class/cache/disposition, explicit endpoint/credentials, and no ACL/AWS-specific extras or multipart operations.
- 412 existing identical → verified reuse; 412 different → MEDIA_UNAVAILABLE; 409/timeout then matching origin read → success; confirmed absent → bounded conditional retry; 403/unknown response never treated as absence.
- No SDK response path calls unconditional PUT, DeleteObject, CopyObject, or alternate-key save.
- ETag/custom metadata alone cannot satisfy verification; return incorrect bytes with a plausible ETag to prove rejection.
- Missing/wrong object Content-Type or required delivery metadata fails closed; no metadata-repair write.
- Locks enabled: duplicate content can be reused, replacement/deletion denied in the disposable development probe; origin bytes remain exact.
- Exact dependency versions are exercised against live US-endpoint R2; streaming/checksum incompatibilities cannot be worked around by dropping the write condition.

### Application integration, configuration, and delivery

- Store verified bytes, create ProductImage inside a test transaction, force DB failure: no image row commits, existing rows remain unchanged, stored object remains readable. This is a T08 assembly test, not a T12 importer implementation.
- Existing T05 UUID/parent/primary/PROTECT behavior and T06 Organization lock tests remain green.
- Admin key field is immutable to legitimate and forged requests; add/raw replacement is unavailable; metadata editing remains scoped/superuser-only; deleting an image association retains object bytes.
- Changing only MEDIA_PUBLIC_BASE_URL changes generated URL without DB writes; URL generation makes no provider request; invalid keys cannot change host/path/query.
- Production rejects local/memory; disabled never falls back; missing required s3 settings fail configuration; builds/collectstatic never contact a provider; secrets never reach rendered settings/errors/frontend.
- Local GET/HEAD returns correct bytes/headers, does not list files, rejects writes, and route is absent in production.
- Live hosted acceptance: valid custom-domain GET/HEAD without credentials; exact hash/MIME/nosniff; TLS; r2.dev disabled; root nonlisting; public writes do not mutate; environment credentials isolated.
- Request a new key before uploading it, then upload valid bytes: custom domain must deliver the object without a lingering cached 404. Verify warm-cache content remains identical. These live checks cannot be claimed from SDK mocks.

## 14. Acceptance criteria

T08 application work passes when verification is side-effect free, both implemented adapters satisfy conformance, immutable writes/readback are proven, ProductImage remains provider-neutral, local media survives container recreation, raw admin key entry is closed, and no T09/import/UI feature has been added.

T08 delivery passes only when T08-H has established and verified both environment buckets, US jurisdiction, Standard class, scoped credentials, bucket protection, live custom domains, disabled r2.dev, production-safe runtime settings, and successful live tests through origin and custom domain. A merged code PR with unconfigured storage is **application complete / Hosting blocked**, not completed T08.

Run backend pytest on PostgreSQL, Django checks, deployment configuration checks, migration drift check (expect no migration), exact-image build/security checks, and the relevant Vite proxy test/build checks. Follow the repository's Validation Summary with Backend, Frontend, Infrastructure/Build, and Human/UAT results. Report mock versus live evidence separately. No tests or infrastructure acceptance were executed as part of this design review.

## 15. Explicit non-goals

No T09 export, T12 import, T16 ProductCard image presentation, native upload UI/API, presigned downloads, private-media authorization, generic Media database model, audio/video/download/transcoding/live-stream implementation, automatic thumbnails/optimization, workers/queues, multipart ingestion, provider migration tooling, GC, refcount deletion, or catalog/domain schema migration.

No automatic bucket creation in SDK constructors, Django startup, migrations, tests, or application requests. No Cloudflare/R2 fields in ProductImage. No AWS infrastructure, IAM/KMS design, or switch to Railway buckets. No bucket-wide listing used to determine an individual object's identity. No public package/quarantine storage.

## 16. Hard-stop conditions

Stop the affected work and report the exact unmet condition; do not change the human decisions or weaken the contract:

1. `us` jurisdiction cannot be created/read back, or the selected endpoint/bucket is outside it. Do not substitute `enam`, Automatic, or another jurisdiction.
2. The media hostname is occupied, belongs to a different account/zone, cannot bind to the selected bucket, or TLS cannot be established. Do not overwrite DNS or silently switch to r2.dev.
3. Conditional creation is unsupported/dropped by the selected SDK/provider, or origin readback cannot prove immutable-content semantics. Do not ship HEAD→unconditional PUT.
4. Existing bytes or required object metadata disagree at a computed key. Do not overwrite, delete, or rename around the failure.
5. Existing ProductImage keys require legacy migration or refer to unrecoverable bytes. Preserve rows; request the missing source/migration decision for that environment.
6. Local filesystem persistence, safe atomic publication, or cross-process locking cannot be established; production is configured with local/ephemeral storage; decoder support or limits are missing.
7. Credential/account/environment scope cannot be proven, or permission would require changing unrelated resources. Complete independent application work while Hosting remains blocked.
8. Required custom-domain delivery headers/error-cache policy or direct read/write boundaries fail live tests. Report code and Hosting status separately.
9. A proposed fix requires ProductImage schema redesign, a storage migration, a private-media model, or implementing T09/T12/T16. Return for focused review rather than expanding T08.

Current review has no evidence that any of these conditions actually exists in the live account: infrastructure was not inspected or changed. They are concrete implementation stop conditions, not requests for another blanket approval.

## 17. Exact implementation order for Luna Medium

All paths below are under `/home/forge/dev/repos/commerce-architect/`. Implement only after the user requests T08 execution.

| Step | Layer and exact objective | Likely files | Required completion evidence |
|---|---|---|---|
| T08-A1 | Application: freeze two-operation storage contract, value objects, key validation, stable media errors, separate delivery policy | `backend/media_storage/__init__.py`, `contracts.py`, `keys.py`, `delivery.py`; `backend/tests/test_media_contract.py` | Pure key/URL/error tests; no Django models or SDK imports in contracts |
| T08-A2 | Application: strict Product-image verification and all-assets-before-write package helper | `backend/catalog/media.py`, `backend/catalog/portability/images.py`; `backend/tests/test_catalog_image_verification.py`; requirements files | Real-format adversarial fixtures; existing schema limits; original bytes preserved; zero-write validation tests |
| T08-P1 | Provider adapter: persistent local implementation and deterministic in-memory test double | `backend/media_storage/local.py`; test-only double; `backend/tests/test_media_local.py` | Shared conformance plus two-process atomicity/persistence/symlink tests |
| T08-P2 | Provider adapter: S3-compatible R2 implementation with explicit condition, bounded retries, and origin verification | `backend/media_storage/s3.py`; `backend/tests/test_media_s3.py`; requirements files | Recorded SDK assertions for all critical branches, no forbidden fallback; locked dependency/image capability checks |
| T08-A3 | Application/configuration: allowlisted lazy factory, environment checks, local volume/serving/proxy, admin raw-key closure | `backend/media_storage/configuration.py`; `backend/config/settings.py`, `urls.py`; `backend/catalog/admin.py`; `backend/media_storage/views.py`; `backend/Dockerfile`; `docker-compose.yml`; `.env.example`; `frontend/vite.config.ts`; affected tests | No migration; production cannot serve/use local media; existing catalog/static/auth behavior preserved; admin security tests |
| T08-A4 | Application integration: media-write then catalog rollback assembly, no-delete lifecycle, end-to-end adapter tests | `backend/tests/test_catalog_media.py`; `backend/tests/test_media_configuration.py` | PostgreSQL assembly/invariant tests and exact-image checks pass; no importer/exporter created |
| T08-H1 | Hosting: account/domain preflight, two Standard US buckets, per-environment object credentials, bucket guards | Existing private Hosting runbook; provider settings and secret store | Sanitized readback proves actual resources, jurisdiction/class/scope; no domain code changes |
| T08-H2 | Hosting: custom domains, TLS, nosniff, explicit success caching/no negative caching, no transforms, r2.dev disabled | Provider domain/cache/header settings; private Hosting record | Domain policy and read-only unauthenticated delivery proven |
| T08-H3 | Hosting/deployment: runtime variables; hosted-development deploy/live conformance; existing production promotion/live smoke | Backend environment configuration; existing release workflow, only necessary tested adjustments | Same tested image digests promoted; origin/domain/environment isolation verified; no live credentials in PR CI |
| T08-A5 | Documentation and closeout: record implemented T08 boundary and exact validation status | `docs/CATALOG_PORTABILITY.md`, `docs/BUILD_DEPLOY.md`, `docs/DOCKER_SETUP.md`, `backend/README.md`; private Hosting runbook | Application/provider/Hosting results separately reported; T08 marked complete only when all pass; stop before T09 |

Hosting preflight and resource preparation may begin after the contract is accepted and before code completion, but no application runtime begins using unverified storage. This ordering is a dependency plan, not an instruction to spawn agents or provision anything during the present review.

The final implementation must deliver **verified original image bytes → immutable provider-neutral key → configurable public delivery**, with database association handled by the existing catalog boundary. Preserve all T01–T07 contracts and stop when T08 plus its required Hosting step is accepted.
