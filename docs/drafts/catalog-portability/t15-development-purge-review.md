# T15 development purge: destructive-boundary review

Status: focused design/refinement artifact for T15. It does not replace `docs/CATALOG_PORTABILITY.md` and does not authorize any other destructive operation.

## 1. Decision summary

T15 is ready for Luna to implement. No schema or migration change is needed, and no human decision remains.

The exact deletion graph is deliberately small: delete the selected Organization's `ProductImage` rows, then its `Product` rows. No Organization, receipt, account, session, admin log, token, through row, future commerce row, or other model may be deleted, nulled, defaulted, or otherwise changed. The successful T15 receipt is the only permitted write outside those two deletion sets.

The Organization lock is necessary but insufficient by itself. A future external writer need not participate in that lock and could otherwise insert a referencing row between a reference scan and a cascading delete. T15 must therefore acquire PostgreSQL `SHARE ROW EXCLUSIVE` table locks on the two target tables and every reviewed referencing/through/generic-reference table before its final scan. That lock mode conflicts with the `ROW EXCLUSIVE` lock taken by `INSERT`, `UPDATE`, and `DELETE`, closing the time-of-check/time-of-delete gap while ordinary reads remain possible. The existing five-second local lock timeout applies; timeout is `CATALOG_BUSY`. See PostgreSQL's [table-level lock matrix](https://www.postgresql.org/docs/current/explicit-locking.html#LOCKING-TABLES).

Safety is established by three checks used together:

1. Django metadata discovery, including hidden reverse relations and standard `GenericForeignKey` declarations;
2. a small purge-specific registry that classifies every discovered relation as the sole internal deletion edge or a reviewed external blocker scanner;
3. PostgreSQL catalog introspection that rejects inbound foreign-key constraints not represented by the reviewed metadata.

Django's deletion collector remains a final assertion. It is not the authority that decides whether cascading or nulling external data is acceptable.

## 2. Current repository facts

- T06's `catalog_write_lock()` opens `transaction.atomic()`, sets `lock_timeout` to five seconds, locks the explicit Organization row with `SELECT FOR UPDATE`, and maps PostgreSQL SQLSTATE `55P03` to `CatalogBusyError`.
- T11's immutable `CatalogOperationReceipt` has all fields T15 needs. Receipt collision recovery is already available outside a rolled-back transaction. Receipts reference Organization, not Product/ProductImage, so purge cannot collect them.
- T12 factored planner helpers for lock-aware target-row capture, state tokens, and target digest reconstruction without media I/O under the Organization lock.
- T13's reset service is the closest service pattern: preview, explicit target digest and Organization confirmation, early and under-lock receipt checks, state-token revalidation, receipt-last transaction, and unknown-outcome resolution. T15 must reuse this structure but performs deletes only after stronger reference checks/table locks.
- T14 provides the command boundary, bounded JSON helpers, operation-ID parsing, status lookup, general `CATALOG_PORTABILITY_ENABLED` guard, and exit-code mapping. No HTTP purge route exists or should be added.
- `Product` is scoped to Organization. `ProductImage.product` uses `PROTECT`; ProductImage identity is scoped to its Product. Existing receipt and Organization foreign keys do not point to Product or ProductImage.
- The current reverse catalog relation set is only `Product.images`; ProductImage has no reverse relations. There are no Orders, Carts, or catalog many-to-many relationships.
- `compatibility.py` already rejects unknown Product/ProductImage reverse relations for normal portability. T15 needs a stricter, independent classification because adding a relation to normal portability's supported set must never authorize purge behavior.
- Django admin is installed and `admin.LogEntry` stores the modified object's ContentType and textual object ID. It must be explicitly represented as a ContentType-style reference spec and a matching log row must block purge. See Django's [`LogEntry` field contract](https://docs.djangoproject.com/en/dev/ref/contrib/admin/#logentry-objects).
- Current settings expose `COMMERCE_ENV`, `IS_PRODUCTION`, and `CATALOG_PORTABILITY_ENABLED`. The accepted T15 flag `CATALOG_ALLOW_DESTRUCTIVE_RESET` does not yet exist.
- The current error enum already includes `REFERENCED_CATALOG`, `UNSUPPORTED_SCHEMA`, `STALE_TARGET`, `OPERATION_NOT_ALLOWED`, `OPERATION_ID_CONFLICT`, `CATALOG_BUSY`, `IMPORT_FAILED`, and `OUTCOME_UNKNOWN`.

The preserved packet is refinement authority for T15; current `docs/CATALOG_PORTABILITY.md` remains schema/media authority and does not itself define destructive purge behavior.

## 3. Allowed deletion graph

The candidate sets are fixed from the locked target snapshot:

```text
candidate_products = Product where organization_id == selected Organization
candidate_images   = ProductImage where product_id in candidate_products
```

The row allowlist is exactly:

| Model | Allowed rows | Operation |
|---|---|---|
| `catalog.ProductImage` | `candidate_images` only | Physical row deletion |
| `catalog.Product` | `candidate_products` only | Physical row deletion after images |
| `catalog.CatalogOperationReceipt` | One new T15 success row | Insert only; existing rows retained |

The sole allowed ownership/deletion edge is `ProductImage.product -> Product`. Because that field is `PROTECT`, T15 explicitly deletes candidate images before candidate Products. It does not change the field's model policy.

Nothing else is an allowed cascade. This includes auto-created or custom many-to-many through rows, even when Django calls them auto-created; external child rows whose foreign key uses `CASCADE`; rows that would be modified by `SET_NULL` or `SET_DEFAULT`; and rows reached by a custom deletion handler. A populated external reference blocks the complete purge.

Before the first `DELETE`, build a Django `Collector` view of the combined image/Product candidate set and inspect its complete proposed effects. `collector.data` may contain only the exact candidate Product and ProductImage PKs. `fast_deletes` may target only those exact sets. Any `field_updates`, `restricted_objects`, protected objects, or collected model outside the allowlist blocks. The metadata/registry scan remains primary; the collector is a defense-in-depth assertion against a missed ORM effect.

After those checks, execute ordinary scoped deletes for candidate images and then candidate Products. Verify the returned per-model delete counts contain no outside model. Any surprise raises and rolls the transaction back. Do not use `_raw_delete`, `TRUNCATE`, `flush`, sequence SQL, or database-drop operations.

## 4. External-reference detection algorithm

Add purge-specific declarations to `catalog.portability.compatibility`; do not reuse `SUPPORTED_PRODUCT_RELATIONS` as a deletion allowlist.

The declarations should represent:

- `PURGE_INTERNAL_DELETE_EDGES`: exactly `catalog.ProductImage.product -> catalog.Product`;
- `PURGE_EXTERNAL_RELATION_SPECS`: reviewed FK, one-to-one, and many-to-many/through relations that T15 knows how to scan but will never delete or modify;
- `PURGE_GENERIC_REFERENCE_SPECS`: exact `(model label, content-type field, object-ID field)` declarations for discovered standard `GenericForeignKey` fields and reviewed ContentType-style pairs, initially including Django admin's `LogEntry` pair;
- a small registry of explicit inspectors for a future reviewed custom reference mechanism that Django metadata cannot express. The current registry is empty.

At preview and apply, discovery operates as follows:

1. Read `Product._meta.get_fields(include_hidden=True)` and `ProductImage._meta.get_fields(include_hidden=True)`. This finds reverse `ForeignKey`, `OneToOneField`, and many-to-many relationships, including hidden auto-created through relations. Django documents the reverse and hidden-field behavior in the [model `_meta` API](https://docs.djangoproject.com/en/6.0/ref/models/meta/#retrieving-all-field-instances-of-a-model).
2. Match the one exact internal edge. A changed target/source field, parent link, multi-table inheritance relation, or additional internal relation is unsupported until reviewed.
3. Match every other direct relation to an exact external relation spec. An unregistered relation is `UNSUPPORTED_SCHEMA` even if its table is empty. A registered relation is only permission to inspect it, never permission to cascade it.
4. For FK and one-to-one specs, query the referencing model's concrete field against candidate PKs. Any populated row is `REFERENCED_CATALOG`, regardless of `on_delete` (`CASCADE`, `PROTECT`, `RESTRICT`, `SET_NULL`, `SET_DEFAULT`, or `DO_NOTHING`). Unknown/custom `on_delete` callables are `UNSUPPORTED_SCHEMA` until explicitly covered.
5. For a many-to-many relation, identify its exact through model and concrete FK to Product/ProductImage. Any matching through row is `REFERENCED_CATALOG`. Ambiguous through mappings, unsupported composite/custom keys, or an unregistered through model are `UNSUPPORTED_SCHEMA`.
6. Scan every installed model's private fields for standard `GenericForeignKey`, then combine those discoveries with explicitly registered ContentType-style pairs such as `admin.LogEntry`. Every discovered standard triple must exactly match `PURGE_GENERIC_REFERENCE_SPECS`; an unregistered generic field is `UNSUPPORTED_SCHEMA`. For each registered spec, resolve the Product and ProductImage `ContentType` values, prepare the integer candidate PKs through the object-ID model field, and query each target type separately. Any match is `REFERENCED_CATALOG`. Django's [contenttypes contract](https://docs.djangoproject.com/en/6.1/ref/contrib/contenttypes/#generic-relations) confirms that the object-ID storage type varies and must be able to coerce the target PK.
7. Inspect PostgreSQL `pg_constraint`/catalog metadata for every foreign key whose referenced table is `catalog_product` or `catalog_productimage`. Compare table, source columns, target columns, and constraint identity with the Django-discovered reviewed set. Any inbound database constraint absent from the reviewed set is `UNSUPPORTED_SCHEMA`, including constraints from unmanaged or stale tables.
8. Run registered custom inspectors. Each must declare the table(s) it reads, a bounded deterministic blocker result, and the target identity representation. An unknown configured integration, missing inspector, unexpected table, or inspector that cannot prove completeness is `UNSUPPORTED_SCHEMA`.

Normal Django metadata can reliably reveal ORM-declared FK, one-to-one, reverse, many-to-many/through, parent-link, and standard generic fields. Explicit specs cover reviewed ContentType-style pairs that are not standard private fields. PostgreSQL introspection can reveal actual database foreign-key constraints outside ORM metadata. None can infer that an arbitrary text/integer/JSON value semantically names a Product without a declared relation. Such a custom mechanism must register an inspector as part of the feature that introduces it; privileged tables and undeclared semantic references are outside what any generic purge can infer.

The registry is an explicit review boundary, not a plugin system. T15 needs no dynamic imports from settings and no general deletion framework.

Reference results are sorted by target model, referencing model, field/relation, and error code. Preview returns at most 100 blockers, plus `total_blocker_count` and `blockers_truncated`. It reports counts, relation identity, and code; it does not enumerate durable row contents.

## 5. Future-domain fail-closed rule

A future `OrderItem`, `CartItem`, reservation, inventory record, or other model with an FK/one-to-one/many-to-many relation to Product/ProductImage creates a reverse relation. Until T15's registry is explicitly reviewed and updated, relation discovery returns `UNSUPPORTED_SCHEMA` before any deletion, even when the new table has no rows. Merely adding that relation to the general portability compatibility set does not satisfy T15.

After review, registering the relation only enables a complete blocker scan. If any candidate is referenced, purge returns `REFERENCED_CATALOG`. Historical commerce references are expected to remain blockers permanently; registering them must never add their rows to the deletion allowlist.

A future standard `GenericForeignKey` similarly fails until its exact field triple is registered. A future raw database FK fails PostgreSQL constraint parity even if Django does not expose it. A custom reference representation must ship with an explicit T15 inspector and tests; configuring an unknown integration fails closed.

Orders and Carts need no implementation for T15. Test-only relation models prove these rules and must not be treated as production domain support.

## 6. Preview and apply transaction sequence

### Validate-only preview

1. Enforce the development/purge feature guard before resolving the Organization.
2. Resolve the explicit active Organization and run current catalog compatibility plus purge-specific relation/generic/constraint compatibility checks.
3. Capture the current catalog snapshot and digest with the existing planner helpers. Existing immutable media is read only as required by current digest semantics; no storage is written or deleted.
4. Determine candidate Product/Image counts and scan all reviewed external references. The preview is advisory, so this scan need not hold locks through operator think time.
5. Return `organization_id`, `target_digest`, `product_count`, `product_image_count`, `valid`, bounded blockers, total blocker count, and truncation. Write no domain row, receipt, file, or media object.

An unknown relation/constraint/reference shape is a compatibility error, not a “zero blockers” preview.

### Apply

1. Enforce the development/purge guard. Validate positive Organization ID, UUIDv4 operation ID, canonical expected digest, and exact literal confirmation `PURGE-CATALOG:<organization-id>`.
2. Compute the semantic fingerprint and perform an early receipt lookup. Exact success returns the prior receipt; changed inputs return `OPERATION_ID_CONFLICT`. The environment guard still runs first, so a prior development purge cannot be replayed through this service in production.
3. Resolve the active Organization, run compatibility, capture/verify the preflight target snapshot, and compare its digest to the expected digest. Optionally run the advisory reference scan for early diagnostics.
4. Enter `catalog_write_lock(organization_id)`. Recheck active status and the environment/purge guard. Recheck the receipt before stale/reference checks.
5. While holding the Organization lock, acquire `SHARE ROW EXCLUSIVE` on `catalog_product` and `catalog_productimage` first, using quoted metadata-derived table names in deterministic order. This prevents new target rows and freezes inbound-FK DDL against the targets.
6. Rediscover and validate ORM relations, generic fields, and PostgreSQL inbound constraints. Determine every reviewed referencing/through/generic/custom-inspector table. Lock those tables in deterministic qualified-name order with `SHARE ROW EXCLUSIVE`. Do not accept a table name from command input or settings.
7. Recapture target rows under the lock, compare the T12 state token with preflight, reconstruct the digest from preverified immutable media, and require it to equal `expected_catalog_digest`. Mismatch is `STALE_TARGET`.
8. Re-run all external-reference queries after every required table lock is held. Any populated known reference is `REFERENCED_CATALOG`; any incomplete/unknown shape is `UNSUPPORTED_SCHEMA`.
9. Build and inspect the combined Django deletion collector. Require the exact allowlisted graph and zero external updates/restricted/protected effects.
10. Delete only candidate ProductImage rows, then only candidate Product rows. Check ORM delete results against the allowlist and expected counts.
11. Assert both candidate sets are empty, Organization and all pre-existing receipts still exist, and no outside row was intentionally touched. Compute the canonical empty-catalog post digest with the existing pure snapshot helper.
12. Insert `catalog-dev-purge` receipt last, in the same transaction.
13. Commit and return only after commit acknowledgement. No after-commit action is required.
14. Resolve receipt uniqueness and ambiguous transaction outcomes outside the failed transaction using T12/T13's existing receipt pattern.

The table locks are intentionally coarse. T15 is a rare development-only operation, and correctness is more important than concurrent write throughput. Ordinary reads remain possible. Writers may wait or receive the existing five-second `CATALOG_BUSY` outcome.

## 7. Receipt and idempotency semantics

Use operation type `catalog-dev-purge`.

The semantic fingerprint contains:

- selected Organization ID;
- operation type `catalog-dev-purge`;
- expected catalog digest;
- exact literal confirmation.

Mode, package hash, and inventory policy remain null because they do not apply. Store `expected_catalog_digest` and `pre_catalog_digest` as the accepted preview digest. Store `post_catalog_digest` as the canonical empty-catalog digest. Store result counts as exactly `products_deleted` and `product_images_deleted`.

An exact successful retry returns the immutable prior receipt without locking or deleting again, after the development guard and input validation. Reusing the ID with another Organization, digest, operation type, or confirmation is `OPERATION_ID_CONFLICT`. Empty-catalog purge with a new operation ID is a valid zero-delete success with a new receipt.

Receipt insertion is last. Any failure before commit leaves no new receipt and rolls back all deletes. If commit acknowledgement is lost, resolve by operation ID on a usable connection: exact receipt means success; proven absence means `IMPORT_FAILED`; inability to establish either state is `OUTCOME_UNKNOWN`. The caller must retain and retry/query with the same operation ID while outcome is unknown.

Every existing receipt survives because receipts are outside the deletion graph. T15 never purges its own or another operation's receipts.

## 8. Environment and confirmation guards

Add one setting only:

```python
CATALOG_ALLOW_DESTRUCTIVE_RESET = env_bool(
    "CATALOG_ALLOW_DESTRUCTIVE_RESET",
    False,
)
```

The service guard requires all of:

- `settings.COMMERCE_ENV == "development"`;
- `settings.IS_PRODUCTION is False`;
- `settings.CATALOG_ALLOW_DESTRUCTIVE_RESET is True`.

`DEBUG` is irrelevant and cannot bypass the guard. The command also uses T14's existing `CATALOG_PORTABILITY_ENABLED` guard. Keep `CATALOG_ALLOW_DESTRUCTIVE_RESET=false` in `.env.example` and do not enable it in Compose defaults.

Add only the accepted command `catalog_dev_purge`:

- always require `--organization`;
- `--validate-only` accepts no apply-only options;
- apply requires `--operation-id`, `--expected-catalog-digest`, and `--confirm-purge`;
- `--confirm-purge` must equal the literal `PURGE-CATALOG:<organization-id>` with exact case and no trimming/substitution;
- expose no `--force`, API, admin action, interactive prompt, or alternate confirmation.

Both preview and apply enforce the environment/feature guard in the service. The command cannot be the only protection.

## 9. Error and result contract

| Condition | Error code | Command class/exit |
|---|---|---|
| Production/production-security mode, disabled destructive flag, inactive Organization, invalid UUID/digest, invalid confirmation | `OPERATION_NOT_ALLOWED` | Forbidden, exit 4 for policy/guard failures; syntactically missing command arguments remain exit 2 |
| Expected digest differs under apply lock | `STALE_TARGET` | Target conflict, exit 3 |
| Populated reviewed external relation/generic/custom reference | `REFERENCED_CATALOG` | Target conflict, exit 3 |
| Unregistered relation/generic field, unknown DB FK, unsupported relation shape, incomplete custom inspector | `UNSUPPORTED_SCHEMA` | Invalid/unsupported, exit 2 |
| Five-second Organization or table-lock timeout | `CATALOG_BUSY` | Target conflict/busy, exit 3 |
| Exact operation ID retry | No error | Original success receipt, exit 0 |
| Changed semantic input with used operation ID | `OPERATION_ID_CONFLICT` | Conflict, exit 3 |
| Rolled-back deletion/receipt transaction | `IMPORT_FAILED` | Operational failure, exit 5 |
| Commit result cannot be established | `OUTCOME_UNKNOWN` | Operational/unknown, exit 5 |

Update `_catalog_operator.command_error_for()` so `REFERENCED_CATALOG` maps explicitly to exit 3. Existing mappings cover the other codes.

Validate-only JSON uses `status: "valid"` when there are no blockers and `status: "invalid"` otherwise, with the preview payload and bounded blocker metadata. Apply success uses T14's existing receipt payload. Errors are deterministically ordered and bounded at 100; never dump referenced row data.

## 10. PostgreSQL test matrix

The minimum acceptance suite is **32 cases in nine major groups**. Transaction, explicit-lock, foreign-key, collector, and race claims run on real PostgreSQL with separate connections where needed.

| Group | Cases | Required coverage |
|---|---:|---|
| Environment and command guards | 5 | Development + both flags + literal confirmation succeeds; production denied despite destructive/general flags and manipulated `DEBUG`; development without destructive flag denied; confirmation mismatch denied; command exposes validate/apply separation and no force option. |
| Preview purity | 3 | Candidate counts/digest and zero mutation; populated registered reference appears as bounded blocker; empty catalog preview is valid and writes no receipt. |
| Allowed deletion boundary | 5 | Organization A Products/images deleted and B byte-for-byte unchanged; ProductImage-before-Product behavior; all old/new receipts retained; immutable media remains readable; sequence is not reset and a later Product receives a new higher PK. |
| ORM external references | 7 | Populated FK `CASCADE`, FK `PROTECT`, FK `RESTRICT`, FK `SET_NULL`, one-to-one, implicit M2M through, and custom through all block with no mutation. Include null `SET_NULL` rows as a non-reference control. |
| Generic, unknown, and future references | 3 | Registered standard generic reference blocks; unregistered generic/custom relation shape fails `UNSUPPORTED_SCHEMA`; a dynamically installed future FK model or raw inbound DB constraint blocks without changing T15's deletion allowlist. |
| Atomic rollback | 2 | Inject failure after image deletion/before Product deletion; inject receipt insertion failure after all deletes. Both restore every candidate row/value and create no receipt. |
| Receipt/idempotency/outcome | 3 | Exact operation ID returns the original receipt without delete queries; changed semantic input conflicts; simulated lost acknowledgement resolves present/absent/unavailable receipts to success/`IMPORT_FAILED`/`OUTCOME_UNKNOWN`. |
| Concurrency and TOCTOU | 2 | Reference committed after preview but before apply is found by the under-lock scan; insert attempted after locked scan cannot sneak through (it blocks, then fails its FK or occurs only after purge), and purge never cascades it. |
| Output and global invariants | 2 | More than 100 blockers are deterministically truncated with total count; SQL/write capture proves no unrelated table changes apart from the new receipt. |

Use test-only Django models and temporary PostgreSQL tables/constraints with deterministic setup/teardown to exercise deletion policies. Register a relation only in the test's purge reference spec when testing a known populated blocker. Leave it unregistered when testing the future-model stop condition. These fixtures do not introduce production Orders or migrations.

## 11. Luna implementation boundaries

### Add

- `backend/catalog/portability/dev_reset.py`: preview/apply services, exact guard, relation discovery/scanning, table-lock protocol, collector assertion, scoped deletes, and receipt/outcome handling.
- `backend/catalog/management/commands/catalog_dev_purge.py`: T14-style validate/apply command.
- `backend/tests/test_catalog_dev_purge.py`: the 32-case PostgreSQL suite and test-only reference models/tables.

### Change

- `backend/catalog/portability/compatibility.py`: purge-only internal edge, external relation, generic-reference, and custom-inspector declarations plus fail-closed discovery helpers.
- `backend/config/settings.py`: one false-by-default `CATALOG_ALLOW_DESTRUCTIVE_RESET` setting.
- `.env.example`: document the same flag as false.
- `backend/catalog/management/commands/_catalog_operator.py`: map `REFERENCED_CATALOG` to target-conflict exit 3 if not handled in the new command.

### Reuse without duplicating

- T06 `catalog_write_lock()` and its five-second timeout/error mapping;
- T12 planner row capture, state-token, media-index/digest reconstruction, and empty snapshot digest;
- T11 receipt fingerprint, lookup, insertion, and post-rollback resolution;
- T13 input/receipt/stale/outcome control flow;
- T14 operation parsing, feature guard, bounded JSON, receipt payload, and error mapping;
- Django metadata and Collector APIs, plus PostgreSQL constraint catalogs and explicit table locking.

Do not duplicate digest serialization, operation fingerprint format, receipt race handling, Organization lookup/locking, or command error conventions. Do not change models or migrations. Do not add Orders, Carts, Customer/CRM, media garbage collection, a general deletion engine, an API/admin surface, background work, `--force`, compensating media deletion, flush/drop/truncate, or sequence reset.

## 12. Exact copy-paste Luna implementation prompt

Implement T15 exactly from `docs/drafts/catalog-portability/t15-development-purge-review.md` on current `develop`. Add `catalog.portability.dev_reset`, the `catalog_dev_purge` management command, and the PostgreSQL acceptance suite; add only the false-by-default `CATALOG_ALLOW_DESTRUCTIVE_RESET` setting and `.env.example` entry; add purge-specific compatibility declarations/scanners and map `REFERENCED_CATALOG` to exit 3. Do not create migrations or change models.

The only deletable rows are ProductImages owned by Products in the explicitly selected Organization and then those Products. No other row may be cascaded, nulled, defaulted, deleted, or updated; existing receipts and all immutable media remain; sequence state is untouched. Treat `ProductImage.product -> Product` as the sole internal edge. Discover hidden reverse FK/O2O/M2M relations from Django metadata, require exact purge-registry classification, scan registered standard GenericForeignKeys and explicit ContentType-style pairs including `admin.LogEntry`, compare inbound PostgreSQL FK constraints with reviewed metadata, and fail `UNSUPPORTED_SCHEMA` on any unknown relation, constraint, generic field, custom shape, or configured inspector. A registered external relation is permission to scan only; any populated reference is `REFERENCED_CATALOG` regardless of on-delete policy.

Preview requires development mode plus the destructive flag, is mutation-free, and returns the target digest, candidate counts, and at most 100 deterministic blockers with total/truncation. Apply requires a UUIDv4 operation ID, expected digest, and the exact literal `PURGE-CATALOG:<organization-id>`. Use operation type `catalog-dev-purge`; fingerprint Organization, operation type, expected digest, and literal confirmation. Return exact receipts early after service guards/input validation and recheck receipt under lock.

For apply, follow T13/T12's preflight snapshot/state-token pattern. Enter the existing Organization lock/atomic transaction, lock Product and ProductImage tables first with PostgreSQL `SHARE ROW EXCLUSIVE`, rediscover inbound constraints, then lock every reviewed referencing/through/generic/custom table in deterministic qualified-name order. Recapture and verify the target digest, run all reference scans only after all locks are held, inspect a combined Django Collector and require exactly the candidate Product/Image graph with no external field updates/restricted/protected effects, delete candidate images then Products, verify counts and empty target state, and insert the receipt last. Resolve insert races and ambiguous commits outside failed transactions. No storage writes or deletes and no after-commit work.

Implement the 32 cases in the nine test groups from section 10 using real PostgreSQL where relationships, rollback, locks, or races matter. Preserve the current behavior of import, preview, reset, status, and other commands. Do not start T16/T17, Operator Experience, Orders, Customer/CRM, browser UI, background jobs, or any generalized deletion/reference framework.
