# T12 atomic import application: final architecture review

Status: design/refinement artifact for the T12 implementation packet. This document records the implementation contract approved by this review. It is not runtime authority and does not replace `docs/CATALOG_PORTABILITY.md`.

## 1. Executive decision

T12 is ready to implement against the contract below. There are no unresolved product or architecture decisions.

The implementation must begin with two narrow prerequisite corrections. They are part of T12's implementation scope, not new architecture:

1. T10's planner currently has no lock-safe way for an importer to recapture rows and rebuild the exact target digest and plan while the caller already holds the Organization lock. Its private `_capture_target_rows()` opens its own lock scope, and `_target_snapshot()` reads storage after that inner scope. Calling it inside T12's outer lock would keep a database transaction and Organization lock open across object-storage reads. T10 must be factored into row capture, verified-media resolution, digest construction, and plan construction so T12 can reuse the same rules with a caller-held lock and a preverified media index.
2. T11's `create_operation_receipt()` catches `IntegrityError` and queries on the same connection. When the insert fails inside T12's outer `atomic()` block, that transaction is marked broken, so the query is unsafe and may raise `TransactionManagementError`. Receipt collision resolution must occur only after the entire mutation transaction has rolled back.

The review deliberately retains the historical architecture: media becomes durable before the database transaction; all catalog row changes and the success receipt commit together; exact request retries use the receipt; content retries use a fresh operation ID; and no rollback path deletes immutable media.

## 2. Current prerequisite reality

### T08: verified immutable media

`backend/catalog/media.py` provides `PreparedImage`, `verify_product_image()`, `verify_package_images()`, `store_verified_product_image()`, and `read_product_image()`. The configured adapters implement content-addressed `put_if_absent()` and bounded verified reads. A successful put returns a `StoredMedia` only after the adapter has established the immutable object and verified its bytes/metadata. Reusing an existing hash key is allowed only when its content is consistent. Storage has no delete operation in this contract.

This satisfies T12's readiness boundary. It cannot make object storage and PostgreSQL one transaction, and does not try to. The application guarantee excludes arbitrary privileged mutation or deletion outside the adapter contract.

### T09: export, not a durable validated-import handle

T09 implemented deterministic, Organization-scoped export in `backend/catalog/portability/exporter.py`. The reusable decoded representation is actually T07's frozen `CatalogPackage` dataclass in `backend/catalog/portability/codec.py`; it holds validated manifest/catalog values and media bytes.

The historical phrase “validated package/import representation from T09” is therefore stale. There is no persisted, provenance-bearing object that proves which exact ZIP bytes produced a `CatalogPackage`. T12 must receive the immutable raw ZIP bytes and compute their SHA-256 itself. It must not accept a caller-supplied `CatalogPackage` paired with an asserted package hash as executable input.

### T10: deterministic preview and reconciliation

`backend/catalog/portability/planner.py` implements modes, stock-policy guards, compatibility checks, target snapshots/digests, deterministic `PlanAction` values, bounded errors, SKU conflicts, authoritative incoming image sets, and replace deactivations without mutation. It verifies package and existing target media.

The current public planner accepts raw ZIP data, streams, decoded packages, or dictionaries. For decoded packages it accepts an optional `package_sha256` without proving that the asserted value is the hash of the original ZIP. That flexibility is acceptable for internal preview tests, but not for T12's apply boundary. The apply service must compute the hash from its own immutable bytes.

The current planner also captures rows while holding the Organization lock and reads their immutable media after releasing it. That produces a coherent preview because the captured keys are immutable, but it is not yet an API T12 can use to revalidate under its already-held lock without storage I/O in the transaction.

### T11: durable success receipts

`CatalogOperationReceipt` already has the required unique operation UUID, protected Organization foreign key, operation type, package/policy/precondition fields, pre/post digests, semantic input fingerprint, result counts, and completion time. Model updates are rejected. `backend/catalog/portability/receipts.py` provides deterministic fingerprinting and exact-retry lookup.

No migration or model change is required for T12. The insert-collision recovery noted in section 1 is the only required T11 correction. Existing sequential exact-retry behavior remains unchanged.

### Models and lock

Product uniqueness is scoped by `(organization, portable_id)` and `(organization, sku)`. ProductImage identity is scoped by `(product, portable_id)`, and PostgreSQL enforces at most one primary image per Product. Product and ProductImage saves use the shared Organization lock. ProductImage cannot be reparented. Product hard deletion is outside this import.

`catalog_write_lock()` opens `transaction.atomic()`, sets PostgreSQL `lock_timeout` to five seconds, and locks the Organization row with `SELECT ... FOR UPDATE`. It maps SQLSTATE `55P03` to `CatalogBusyError`. T12 must use this as its one outer mutation transaction; nested model save scopes are reentrant on the same connection but do not define the operation boundary.

## 3. Exact T12 service contract

Add one backend/domain entry point with the effective contract:

```python
apply_catalog_import(
    package_bytes: bytes,
    organization_id: int,
    *,
    mode: Literal["merge", "replace-storefront"],
    inventory_policy: Literal["preserve", "restore-snapshot"] = "preserve",
    operation_id: uuid.UUID,
    expected_package_sha256: str,
    expected_catalog_digest: str,
    confirmed_organization_id: int | None = None,
    storage_adapter=None,
) -> CatalogOperationReceipt
```

`package_bytes` is the bounded immutable copy used for the whole call. T12 rejects mutable buffers and streams at this boundary; a later command may perform bounded file reading before calling it. The service computes the actual ZIP hash before decoding. `operation_id` must be a caller-generated UUIDv4. Both expected hashes must be lowercase 64-character SHA-256 values.

The caller supplies `expected_package_sha256` and `expected_catalog_digest` from the preview. They are optimistic preconditions, not authorization. `confirmed_organization_id` is required for `replace-storefront` and must equal `organization_id`; it is otherwise `None`. Future operator authentication and permission checks remain outside T12.

The semantic receipt fingerprint contains the exact Organization ID, operation type (`catalog-import`), mode, computed package SHA-256, inventory policy, expected target digest, and canonical confirmation (`str(confirmed_organization_id)` or `None`). Changing any of them while reusing the operation ID is `OPERATION_ID_CONFLICT`.

The output is the committed `CatalogOperationReceipt`. An exact retry returns the original row and original counts/digests/completion time. The service never returns a newly constructed success result before transaction commit.

Use existing `CatalogPackage`, `PreparedImage`, `StoredMedia`, `CatalogPlan`, `PlanAction`, compatibility checks, storage adapter, shared lock, and receipt fingerprint/lookup. A caller's preview `CatalogPlan` is not an input and is never trusted as mutation instructions. T12 recomputes the plan from the package and current target.

Existing portability errors remain the public error vocabulary:

- malformed/unsafe/unsupported package and image errors from T07/T08;
- `PACKAGE_CHANGED` for a ZIP hash that differs from the preview hash;
- `STALE_TARGET` for a target precondition that no longer matches;
- planner conflict codes such as `SKU_CONFLICT`;
- `OPERATION_NOT_ALLOWED` for mode, confirmation, stock-policy, compatibility, or inactive-Organization rejection;
- `OPERATION_ID_CONFLICT` for semantic reuse;
- `CATALOG_BUSY` for the five-second Organization-lock timeout;
- `MEDIA_UNAVAILABLE`, `IMPORT_FAILED`, and `OUTCOME_UNKNOWN` as described below.

## 4. Exact ordered application algorithm

1. Validate primitive inputs: bytes type and ZIP size bound, positive Organization ID, UUIDv4 operation ID, recognized mode/policy, canonical expected hashes, and required replace confirmation.
2. Compute SHA-256 from `package_bytes`. If it does not equal `expected_package_sha256`, return `PACKAGE_CHANGED`. Do not decode, stage media, or touch catalog rows.
3. Build the semantic input fingerprint from the computed hash and exact request values.
4. Query the receipt by operation ID. Return an exact receipt immediately without taking the Organization lock. Fail with `OPERATION_ID_CONFLICT` on a different fingerprint. This lookup is permitted even if catalog state or Organization status later changed.
5. Decode and completely validate the same immutable bytes. Verify all package media and retain the `asset_path -> PreparedImage` map. Run the shared compatibility and stock-policy guard. Build an initial current-target snapshot and plan using T10 rules. If the current digest differs from `expected_catalog_digest`, return `STALE_TARGET`; if the plan contains conflicts, return its deterministic errors. This is an optimization and early failure check, not the commitment check.
6. Retain a preflight database-state token made from the captured Product fields and ProductImage fields including `storage_key`, plus the verified `storage_key -> PreparedImage` index used to derive the target digest. This token is internal and is not a new caller precondition.
7. Stage every distinct package image, in sorted asset-path order, with `store_verified_product_image()`. Retain `asset_path -> StoredMedia`. Verify each returned object agrees with the prepared content hash, size, and content type. A reused object and a newly written object have identical readiness semantics.
8. Enter `catalog_write_lock(organization_id)`. Its `atomic()` scope is the one outer mutation transaction and obtains the Organization row lock with the current five-second timeout.
9. Recheck that the locked Organization is active. Re-run the shared compatibility and stock-policy guards, including the live inventory-protection check. Recheck replace confirmation against the locked Organization ID.
10. Query the receipt again while holding the lock and before stale checks or mutation. An exact receipt means a concurrent same-target request committed while this call staged media; return it by leaving the transaction without writes. A different fingerprint is `OPERATION_ID_CONFLICT`.
11. Recapture all scoped Product and ProductImage rows directly under the already-held lock. Do not call a helper that opens and releases a separate lock. Compare their deterministic database-state token with the preflight token. Any difference is `STALE_TARGET`. When equal, use the preverified immutable target-media index to reconstruct the exact current target digest without storage I/O. It must equal both the preflight digest and `expected_catalog_digest`; otherwise return `STALE_TARGET`.
12. Rebuild the complete `CatalogPlan` from the decoded package and this locked snapshot using T10's single reconciliation implementation. Recheck `plan.package_sha256`, mode, policy, target digest, validity, conflicts, and all staged-media mappings. No caller plan or preflight action list is executed blindly.
13. Apply Product creates and updates in portable-ID order. Preserve the database PK of every match. Save only effective changes. Use zero stock for a new Product under `preserve`; otherwise use the shared plan's effective stock. Never update `portable_id`, Organization, or `product_type` on an existing row.
14. Reconcile the complete image set of each incoming Product in Product portable-ID order and image portable-ID order, using the safe sequence in section 7. Every stored key comes from the staged, verified mapping. Do not reparent an image.
15. In `replace-storefront`, deactivate the locked snapshot's destination-only Products that are currently active. Do this after incoming aggregate reconciliation and change only `is_active` and `updated_at`.
16. Recapture rows under the same lock and run final aggregate assertions: effective incoming Product values, authoritative incoming image sets and storage keys, at most one primary, merge preservation, replace active-set result, and Organization scope. Build the post-catalog digest using the preverified target-media index for untouched objects and staged prepared media for imported objects. No object-store read belongs inside this transaction.
17. Insert one receipt with operation type, computed package hash, policy, expected/pre/post digests, exact plan counts, input fingerprint, and completion time. The insert is the last required database write.
18. Exit the outer transaction. Return success only after `atomic()` completes successfully.
19. Optional cache invalidation may use `transaction.on_commit()`, but its failure cannot change import success and no required storage promotion or correctness action may be placed there.
20. On a receipt uniqueness race or ambiguous commit exception, leave the failed transaction completely, then resolve the operation ID on a usable/fresh database connection as specified in sections 8 and 10.

## 5. Transaction and locking model

```mermaid
sequenceDiagram
    participant Caller
    participant Apply as T12 service
    participant Media as Immutable media
    participant DB as PostgreSQL

    Caller->>Apply: bytes + org/mode/policy + operation ID + preview hashes
    Apply->>Apply: hash, receipt lookup, decode, validate, preflight plan
    Apply->>Media: put_if_absent + verified readiness
    Media-->>Apply: immutable StoredMedia mappings
    Apply->>DB: BEGIN; SET LOCAL lock_timeout = 5s
    Apply->>DB: SELECT Organization FOR UPDATE
    Apply->>DB: receipt recheck + locked row snapshot
    Apply->>Apply: revalidate policy/digest/plan from locked snapshot
    Apply->>DB: Product writes
    Apply->>DB: ProductImage reconciliation
    Apply->>DB: replace deactivations + final aggregate reads
    Apply->>DB: INSERT success receipt
    Apply->>DB: COMMIT
    DB-->>Apply: commit acknowledged
    Apply-->>Caller: committed receipt
```

The Organization row is the serialization point even for an initially empty catalog. No Product lock can replace it. All queries and writes in steps 9–17 are explicitly scoped by Organization; identity lookups never search globally. Product and image ordering is deterministic.

Object-store calls are excluded from the transaction. The lock-safe digest method relies on two facts already established by T08: storage keys are content addressed, and adapter-managed objects are immutable. A changed row/storage-key token is stale; an unchanged token can reuse the media descriptors verified during preflight. This preserves exact digest semantics without holding a PostgreSQL lock during network I/O.

## 6. Media readiness and orphan model

All package image bytes are decoded and verified before the first durable put. Each unique asset path is staged once. `put_if_absent()` may create an object or verify/reuse the existing content-addressed object; T12 treats both as ready only after the adapter returns a matching `StoredMedia`.

If the third of five writes fails, the first two may remain. No database transaction has begun and no ProductImage points at the new mappings. A later retry safely reuses them. If database work later fails, every staged object may remain unreferenced. These objects are acceptable immutable residue: they contain validated package bytes, expose no partial catalog state, and can be shared by another catalog or concurrent import.

Rollback compensation must never delete them. A hash key may already have been referenced before this operation, or may become referenced concurrently by another Organization. Deletion would turn one failed import into broken committed references elsewhere.

Readiness is established immediately before the database transaction. T12 cannot protect against privileged out-of-band object deletion, but a committed ProductImage must use only a key returned by the adapter for the exact prepared bytes. There is no temporary key, after-commit promotion, or database reference to an unverified object.

## 7. Product, image, stock, and replace semantics

### Products and SKU

T10 remains the sole owner of reconciliation and conflict rules. T12 consumes the fresh locked plan; it does not independently invent matching, SKU-cycle, or conflict logic. A matching portable ID updates the same row and therefore retains its PK and creation time. A changed SKU is allowed only when T10 established that no other destination Product, active or inactive, owned it at the start snapshot. T10's conservative rejection of swaps/cycles makes deterministic direct updates safe.

For an actual Product change, save only changed model fields and include `updated_at`. For an effective no-op, do not save. New Products use the incoming portable ID, physical type, local timestamps, and the effective stock value.

### Stock

Under `preserve`, matching Products keep current stock and new Products start at zero. Under `restore-snapshot`, incoming stock is applied to matching and new Products.

The shared guard must execute during preflight and again after the Organization lock is acquired. Restore is allowed only when all are true at both checks:

- `COMMERCE_ENV == "development"`;
- `CATALOG_ALLOW_SNAPSHOT_STOCK_RESTORE is True`;
- the caller explicitly selected `restore-snapshot`;
- the compatibility registry is known and supported;
- no registered inventory protection is active for the target.

The current registry declares no implemented inventory protections. That is an explicit known-empty declaration, not permission to ignore future checks. T12 must call the same guard as T10 so a future registered protection fails closed without duplicated policy code.

### Image aggregate

For each incoming Product, package images are the complete desired set in both modes. Images of destination-only Products are untouched. Resolve image identity only within its matched parent.

Use this mutation order for each incoming Product:

1. Determine current and final primary image IDs from the locked plan/snapshot.
2. If the current primary differs from the final primary, explicitly save the old primary as `is_primary=False` with an updated local `updated_at`. Do not rely on `ProductImage.save()`'s implicit queryset clearing, because that path does not update the cleared row's timestamp.
3. Create new images and update existing non-primary fields using verified staged storage keys. Until the transition is complete, create the new intended primary with `is_primary=False`. Save only rows with effective field changes.
4. Remove omitted ProductImage rows. Clear a removed primary first. Do not delete its storage object.
5. Set the final primary true only after no other row is primary, and update its timestamp if this changes the flag. If the same existing primary remains primary, update its other changed fields without clearing/re-setting it.
6. Re-read and compare the final aggregate to the intended records.

An empty incoming image set clears the current primary if necessary and removes every image row for that incoming Product. A failure anywhere rolls the clear, inserts, updates, and removals back together.

### Replace storefront

The destination-only set is `locked_target_product_portable_ids - incoming_product_portable_ids`. For each member, change `is_active` from true to false only. Retain PK, Organization, portable ID, SKU, stock, all other Product fields, every ProductImage row, and every storage object. Do not save rows already inactive, so their timestamps remain unchanged.

The final active identity set is exactly the incoming Products whose package status is active. Incoming inactive Products remain or become inactive through normal aggregate reconciliation.

## 8. Receipt and retry semantics

Receipt lookup follows hash verification and precedes package decode, media staging, and the Organization lock. Hashing the supplied bytes is necessary to prove that the request actually carries the package named by its semantic fingerprint. An exact successful retry can therefore avoid all expensive validation and locking, while a changed byte stream cannot borrow an old receipt by asserting its old hash.

The second receipt check under the Organization lock closes the interval between early lookup and mutation. It must occur before target-digest comparison: a concurrent exact request may have legitimately changed the target and committed the receipt, and the waiter must receive the prior success rather than `STALE_TARGET`.

The unique `operation_id` constraint is the final arbiter. Same-Organization attempts serialize on the Organization lock and the loser observes the receipt at step 10. Different-Organization attempts do not share that lock, so a global operation-ID collision can happen at insert. Any insert `IntegrityError` aborts and rolls back the whole import transaction. Only after rollback may the service query the operation ID: matching fingerprint returns the committed receipt; different fingerprint returns `OPERATION_ID_CONFLICT`; no receipt means the insert failed for another reason and the caller receives `IMPORT_FAILED`.

Content idempotence and request idempotence are distinct:

- **Content idempotence:** applying the same effective package state with a new operation ID produces no Product/ProductImage saves for equal values and no entity timestamp churn. It commits a distinct receipt. The expected target digest is necessarily the digest of the current state used for that second preview.
- **Request idempotence:** retrying a successful operation ID with all semantic inputs and bytes unchanged returns the original receipt without replay, even if the catalog later changed. It creates no row, timestamp, or media changes.

No receipt represents failure, validation, or an unknown outcome. A success receipt exists if and only if its catalog mutation committed.

## 9. Concurrency analysis

| Race | Required result |
|---|---|
| Two imports use the same preview digest and different operation IDs | Both may preflight/stage concurrently. The first lock holder may commit. The second recaptures a changed token and fails `STALE_TARGET`. If the first import was an effective content no-op, the digest/token remains equal and the second may also commit a no-op plus its own receipt. |
| Two imports target an initially empty Organization | The Organization row exists and serializes them despite no Product rows. The second sees the first's inserts and either becomes stale or builds the valid current no-op/conflict result. |
| Same operation ID, same inputs, same Organization | One commits. The other returns the same receipt at the under-lock check, at unique-collision resolution, or on a later retry. Mutation occurs once. |
| Same operation ID, different inputs, same Organization | The committed/observed receipt causes `OPERATION_ID_CONFLICT`. If both started before a receipt existed, Organization serialization ensures only one reaches mutation. |
| Same operation ID across different Organizations | Locks do not serialize them. One global receipt insert wins. The loser's whole transaction rolls back; post-rollback lookup returns `OPERATION_ID_CONFLICT` because Organization is part of the fingerprint. |
| Supported catalog writer races import | The common Organization lock orders the writer and importer. If the writer commits first, import detects stale state. If import commits first, the writer starts afterward. |
| Media staging races before either lock | Content-addressed `put_if_absent()` safely creates or reuses identical objects. Different content has different keys. The later database lock decides catalog order; unused staged bytes may remain as orphans. |
| Target changes and later returns to the exact preflight state | The recaptured deterministic token and digest match, so apply may proceed. Preconditions protect state, not historical absence of intervening transactions. |

These guarantees cover writers that honor `catalog_write_lock()` and media writers that honor the immutable adapter contract. Privileged SQL or out-of-band object mutation remains outside the application guarantee.

## 10. Failure matrix

| Failure point | Database state | Media state | Receipt | Caller outcome | Retry |
|---|---|---|---|---|---|
| Package hash differs from preview | Unchanged | Unchanged | No new receipt; any prior receipt is untouched | `PACKAGE_CHANGED` | Safe with the intended bytes and same ID; changed semantic input with an already-used ID conflicts. |
| Media write/readback fails | Unchanged; transaction not started | Earlier immutable puts may remain orphaned | No new receipt | `MEDIA_UNAVAILABLE` or the existing media error | Safe with same ID; ready objects are reused. |
| Organization lock exceeds five seconds | Unchanged | Staged objects may remain orphaned | No new receipt | `CATALOG_BUSY` | Safe with same ID and original preconditions; it may later become stale. |
| Locked target differs from preview/preflight | Unchanged | Staged objects may remain orphaned | No new receipt | `STALE_TARGET` | Safe only after a new preview/precondition, normally with a new operation ID because the semantic input changed. |
| Product create/update fails | Entire transaction rolled back | Staged objects retained | No new receipt | Preserve a stable domain error where available; otherwise `IMPORT_FAILED` | Safe with same ID and unchanged preconditions after cause is fixed. |
| Image insert/update or content-reference change fails | Entire transaction rolled back | Staged objects retained | No new receipt | `IMPORT_FAILED` or stable constraint/domain error | Safe as above. |
| Image removal fails | Prior Product/image work and removal rolled back | Staged objects retained; no deletion | No new receipt | `IMPORT_FAILED` | Safe as above. |
| Primary clear/switch fails | Clear, switch, and all other database work rolled back | Staged objects retained | No new receipt | `IMPORT_FAILED` | Safe as above. |
| Replace deactivation fails | Incoming reconciliation and all deactivations rolled back | Staged objects retained | No new receipt | `IMPORT_FAILED` | Safe as above. |
| Receipt insertion fails without a competing receipt | All catalog writes rolled back | Staged objects retained | No new receipt | `IMPORT_FAILED` | Safe after the database cause is fixed. |
| Receipt uniqueness race | Losing transaction fully rolled back | Staged objects retained/reusable | Winner's receipt only | Exact fingerprint returns winner's receipt; otherwise `OPERATION_ID_CONFLICT` | Already resolved by receipt; no mutation replay. |
| Definitive transaction commit error/rollback | Unchanged after authoritative resolution | Staged objects retained | None | `IMPORT_FAILED` | Safe with same ID and preconditions. |
| Connection loss during/after COMMIT acknowledgement | Either all catalog rows plus receipt committed, or none committed; never a partial database state | Staged objects retained | Present iff committed | Reconnect and query operation ID. Exact receipt means success; proven absence means `IMPORT_FAILED`; inability to establish either is `OUTCOME_UNKNOWN` | Retry/query with the same operation ID and identical inputs. Never choose a new ID while outcome is unknown. |

A commit exception must not be described as rollback until a fresh authoritative receipt lookup succeeds and finds no receipt. If the database remains unavailable or its state cannot be established, return `OUTCOME_UNKNOWN`. Closing/replacing an unusable Django connection before resolution is an implementation detail; resolution must run outside the failed atomic block.

## 11. PostgreSQL test matrix

All lock, rollback, uniqueness-race, and commit-acknowledgement tests must run against real PostgreSQL. Use `transaction=True`, separate Django connections per thread/process, bounded synchronization primitives, and timeouts. Do not substitute SQLite for transactional claims.

| Area | Required tests and assertions |
|---|---|
| Happy path | Create/update/no-op Products; retain matched PKs and created times; map statuses; authoritative image creation/update/removal; final primary; merge preservation; replace deactivation; exact pre/post digests and counts; one receipt. |
| Stock | Preserve matching stock and zero new stock in both modes; restore stock only with development + explicit flag + no protection; reject production, disabled flag, and active/unknown protection during preflight and when changed before the locked check. |
| Product failure injection | Raise after a Product create and after a Product update. Assert byte-for-byte-equivalent catalog row values/timestamps, no receipt, Organization B unchanged, staged orphan permitted. |
| Image replacement injection | Raise after changing an existing image storage key/metadata. Assert Product and every image row/timestamp roll back; old reference still resolves; staged bytes may remain. |
| Image removal injection | Raise after one omission-driven delete, including an empty incoming set. Assert all removed rows and prior primary return, with no receipt. |
| Primary transition injection | Raise after old-primary clearing and after new-primary setting. Assert exactly the original primary and timestamps remain; no transient state commits. Cover existing-to-existing, existing-to-new, primary removal, and no-primary final states. |
| Replace failure injection | Raise after at least one destination-only deactivation. Assert every activation state/timestamp and all incoming aggregate changes roll back. Already-inactive rows must never be saved. |
| Receipt failure injection | Raise immediately before insert, after the insert but before transaction exit, and via an insert constraint/error. Assert all catalog writes and receipt roll back. The “after insert” hook is essential. |
| Media failure | Fail the Nth `put_if_absent()` or readback. Assert zero DB calls that mutate catalog/receipt; earlier immutable objects may exist; retry reuses them. |
| Preconditions | Changed package bytes with old hash gives `PACKAGE_CHANGED`; target change before call and between preflight/staging/lock gives `STALE_TARGET`; no catalog/receipt mutation. Preview plan object cannot be supplied as authority. |
| Two imports | With barriers, start two imports from the same non-no-op digest. Assert one success and one stale result, one catalog transition, and only the winner's receipt. Repeat on an initially empty Organization. Cover identical content no-op where both distinct IDs may succeed. |
| Duplicate operation ID | Same target/same fingerprint returns one immutable receipt under concurrency. Same target/different input conflicts. Different targets/same ID race causes one commit and complete rollback of the other. Assert no broken-transaction error leaks from receipt handling. |
| Writer race | Hold/release the Organization lock around a supported catalog update. Assert ordering and stale detection. Verify five-second timeout maps to `CATALOG_BUSY`. |
| Lost response | Commit successfully, suppress/raise the simulated response after commit, then call again with the same ID and bytes. Assert the original receipt returns without media puts, lock acquisition, row saves, or timestamp change. |
| Ambiguous commit | Simulate connection loss at commit and exercise both authoritative outcomes: receipt present returns success; receipt absent returns failure; unavailable resolution returns `OUTCOME_UNKNOWN`. |
| Timestamp/content idempotence | Re-preview and apply identical effective state with a new ID. Assert Product/ProductImage `updated_at` values are identical, existing PKs unchanged, and a second receipt exists. Also verify unchanged current primary is not toggled. |
| Scope | Import Organization A with colliding portable IDs/SKUs in B. Assert all B rows, timestamps, images, stock, and receipts are unchanged. Concurrent A/B imports with different IDs do not block each other's Organization locks. |
| Final-state validation | Inject divergence between a planned action and applied aggregate and assert `IMPORT_FAILED` plus total rollback. Verify post-digest equals a fresh out-of-transaction digest after commit. |

Failure hooks should be explicit private test seams at the named phase boundaries, or tightly scoped monkeypatches. Do not add a general workflow/hook framework to production.

## 12. Implementation map

### New files

- `backend/catalog/portability/importer.py`: the T12 entry point, immutable apply preparation, media staging, ordered mutation, final checks, commit/outcome resolution.
- `backend/tests/test_catalog_import_application.py`: the PostgreSQL behavior, rollback, concurrency, idempotence, media, and timestamp suite.

### Existing files to change

- `backend/catalog/portability/planner.py`: extract and reuse one policy guard; expose internal lock-aware row capture and pure target-snapshot/plan construction from supplied rows plus preverified media descriptors. Preserve the existing public preview behavior and output.
- `backend/catalog/portability/receipts.py`: stop querying after an insert `IntegrityError` inside a broken transaction; provide or support post-rollback exact/conflict resolution.

No model or migration change is expected. `backend/catalog/models.py`, `backend/catalog/media.py`, `backend/media_storage/contracts.py`, adapter implementations, schema, exporter, HTTP routes, and command interfaces should remain unchanged unless implementation uncovers a concrete defect that this review did not identify.

### Helpers to reuse

- T07 `decode_package()` and canonical/hash limits;
- T08 `verify_package_images()` and `store_verified_product_image()` plus configured media storage;
- T10 compatibility checks, stock-policy guard after factoring, target record formatting, digest construction, `_make_plan()` reconciliation logic, `CatalogPlan`, and `PlanAction`;
- T06 `catalog_write_lock()` and scoped ownership rules;
- T11 `operation_input_fingerprint()`, `find_operation_receipt()`, and corrected transactional receipt insertion;
- Product/ProductImage validation and PostgreSQL constraints as defense in depth.

Do not duplicate ZIP/schema/image validation, media content hashing, target digest serialization, SKU/conflict detection, mode planning, stock-policy rules, compatibility declarations, semantic fingerprint fields, or Organization-lock behavior in the importer. Refactor shared code with narrow internal helpers instead.

## 13. Resolved decisions

1. Apply accepts immutable raw ZIP bytes, not a preview plan or caller-asserted decoded package/hash pair.
2. The actual ZIP hash is computed before receipt lookup; changed bytes cannot claim an old exact retry.
3. Exact receipt retry may return before Organization lock and package decode, after primitive validation and byte hashing.
4. Replace requires `confirmed_organization_id == organization_id`; the canonical value participates in the receipt fingerprint.
5. Preview is advisory. Plan, policy, compatibility, target state, and conflicts are checked again under the Organization lock.
6. Media is verified/staged before the database transaction. Partial staging and later transaction failure may leave immutable orphans.
7. T12 never deletes media and performs no required storage work after commit.
8. No object-store reads occur while holding the database transaction/Organization lock. A preverified immutable media index plus an under-lock database-state token supplies exact stale detection and digest reconstruction.
9. The locked plan is rebuilt by T10's reconciliation logic and is the only plan used for mutation.
10. Products are updated in place; portable identity, Organization, product type, PK, and creation time are preserved.
11. Stock preserve/restore semantics and every restore guard are enforced twice through one shared service-level guard.
12. The old primary is explicitly cleared with timestamp maintenance before assigning a different primary. Omitted image rows are deleted only from PostgreSQL; bytes remain.
13. Replace changes only active destination-only Products, and only their `is_active`/`updated_at` values.
14. No-op entities are not saved. A distinct successful operation may add a receipt without changing entity timestamps.
15. The receipt insert is the last required database write in the same atomic transaction.
16. Receipt uniqueness collision is resolved only after the losing transaction has completely rolled back.
17. Same-target exact duplicate requests recheck receipt before stale detection; this prevents a committed retry from being mislabeled stale.
18. Ambiguous commit is resolved by the same operation ID on a fresh usable connection; unresolved state is `OUTCOME_UNKNOWN`.

## 14. Open questions and blockers

There are no open architecture blockers.

The two helper defects in sections 1 and 12 are mandatory first steps in the T12 coding thread. They are resolved here at the design level: factor a lock-aware/pure planner path and move receipt collision lookup outside failed transactions. If either cannot be implemented without changing the public preview or receipt semantics described here, stop and return for review rather than weakening atomicity or performing storage I/O under the lock.

## 15. Recommended implementation prompt

Implement T12 from `docs/drafts/catalog-portability/t12-atomic-import-application-review.md`. Add `backend/catalog/portability/importer.py` and PostgreSQL tests, first factoring T10 into a shared stock-policy guard plus lock-aware row capture/pure snapshot-and-plan construction, and correcting T11 so receipt insert collisions are resolved only after full transaction rollback. Accept immutable ZIP bytes and explicit package/target preconditions; hash before receipt lookup; return exact retries early; fully validate and stage immutable media before the Organization transaction; recheck receipt, compatibility, stock guards, target token/digest, and the complete plan under the five-second Organization lock; apply Products, authoritative image aggregates and safe primary transitions, then replace deactivations; validate final state; insert the receipt last; and return only after commit. Preserve PKs and no-op timestamps, never delete media, and implement post-rollback duplicate-ID and ambiguous-commit resolution including `OUTCOME_UNKNOWN`. Do not add migrations, commands, HTTP/UI surfaces, background jobs, generic workflows, or operator capability work.
