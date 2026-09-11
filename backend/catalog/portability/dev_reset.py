"""Fail-closed, development-only deletion of one Organization's catalog."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from django.apps import apps
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.db.models.deletion import (
    CASCADE,
    Collector,
    DO_NOTHING,
    PROTECT,
    RESTRICT,
    SET_DEFAULT,
    SET_NULL,
)

from catalog.models import CatalogOperationReceipt, Product, ProductImage
from catalog.portability.compatibility import (
    PURGE_CUSTOM_INSPECTORS,
    PURGE_EXTERNAL_RELATION_SPECS,
    PURGE_GENERIC_REFERENCE_SPECS,
    PURGE_INTERNAL_DELETE_EDGES,
    PurgeGenericReferenceSpec,
    PurgeRelationSpec,
)
from catalog.portability.errors import CatalogPackageError
from catalog.portability.planner import (
    _capture_target_rows,
    _capture_target_rows_locked,
    _target_snapshot,
    _target_snapshot_from_rows,
    _target_state_token,
)
from catalog.portability.receipts import (
    create_operation_receipt,
    find_operation_receipt,
    operation_input_fingerprint,
)
from catalog.portability.schema import ErrorCode, SHA256_PATTERN
from catalog.services import (
    CatalogBusyError,
    CatalogScopeError,
    catalog_write_lock,
    get_active_organization,
)
from organizations.models import Organization


OPERATION_TYPE = "catalog-dev-purge"
MAX_BLOCKERS = 100


@dataclass(frozen=True)
class PurgeBlocker:
    code: ErrorCode
    identity: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code.value,
            "identity": self.identity,
            "message": self.message,
        }


@dataclass(frozen=True)
class PurgePreview:
    organization_id: int
    target_digest: str
    product_count: int
    product_image_count: int
    valid: bool
    blockers: tuple[PurgeBlocker, ...] = ()
    total_blocker_count: int = 0
    blockers_truncated: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "organization_id": self.organization_id,
            "target_digest": self.target_digest,
            "product_count": self.product_count,
            "product_image_count": self.product_image_count,
            "valid": self.valid,
            "blockers": [blocker.as_dict() for blocker in self.blockers],
            "total_blocker_count": self.total_blocker_count,
            "blockers_truncated": self.blockers_truncated,
        }


@dataclass(frozen=True)
class _PurgeGraph:
    external: tuple[PurgeRelationSpec, ...]
    generic: tuple[PurgeGenericReferenceSpec, ...]
    custom: tuple[tuple[str, Any], ...]
    lock_models: tuple[type, ...]


def _fail(message: str, code: ErrorCode = ErrorCode.OPERATION_NOT_ALLOWED) -> None:
    raise CatalogPackageError(code, message)


def _require_development_purge() -> None:
    if (
        getattr(settings, "COMMERCE_ENV", None) != "development"
        or getattr(settings, "IS_PRODUCTION", None) is not False
        or getattr(settings, "CATALOG_ALLOW_DESTRUCTIVE_RESET", False) is not True
    ):
        _fail("development catalog purge is not permitted")


def _validate_inputs(
    organization_id: int,
    operation_id: uuid.UUID,
    expected_catalog_digest: str,
    confirmation: str,
) -> None:
    if isinstance(organization_id, bool) or not isinstance(organization_id, int) or organization_id <= 0:
        _fail("a positive Organization ID is required")
    if not isinstance(operation_id, uuid.UUID) or operation_id.version != 4:
        _fail("operation_id must be a UUIDv4")
    if not isinstance(expected_catalog_digest, str) or not SHA256_PATTERN.fullmatch(expected_catalog_digest):
        _fail("expected_catalog_digest must be a canonical lowercase SHA-256")
    expected_confirmation = f"PURGE-CATALOG:{organization_id}"
    if confirmation != expected_confirmation:
        _fail("purge confirmation does not exactly match the selected Organization")


def _fingerprint(organization_id: int, digest: str, confirmation: str) -> str:
    return operation_input_fingerprint(
        organization_id=organization_id,
        operation_type=OPERATION_TYPE,
        expected_catalog_digest=digest,
        confirmation=confirmation,
    )


def _label(model: type) -> str:
    return model._meta.label


def _model_for_label(label: str):
    try:
        app_label, model_name = label.split(".", 1)
        return apps.get_model(app_label, model_name)
    except (LookupError, ValueError) as exc:
        _fail(f"purge registry model is not installed: {label}", ErrorCode.UNSUPPORTED_SCHEMA)
        raise AssertionError from exc


def _relation_observations() -> tuple[PurgeRelationSpec, ...]:
    observations: dict[tuple[str, str, str, str, str | None, str | None], PurgeRelationSpec] = {}
    targets = {_label(Product): Product, _label(ProductImage): ProductImage}
    for model in apps.get_models():
        for field in model._meta.get_fields(include_hidden=True):
            if not getattr(field, "is_relation", False):
                continue
            if getattr(field, "remote_field", None) is not None and not (
                getattr(field, "auto_created", False) and not getattr(field, "concrete", False)
            ):
                related_target = field.remote_field.model
                if related_target not in targets.values():
                    continue
                kind = "many_to_many" if getattr(field, "many_to_many", False) else (
                    "one_to_one" if getattr(field, "one_to_one", False) else "foreign_key"
                )
                through = _label(field.remote_field.through) if kind == "many_to_many" else None
                through_field_name = None
                if through:
                    through_model = field.remote_field.through
                    target_fields = [
                        candidate.name
                        for candidate in through_model._meta.get_fields()
                        if getattr(candidate, "remote_field", None) is not None
                        and candidate.remote_field.model is related_target
                    ]
                    if len(target_fields) != 1:
                        _fail(
                            "many-to-many purge relation has an ambiguous through mapping",
                            ErrorCode.UNSUPPORTED_SCHEMA,
                        )
                    through_field_name = target_fields[0]
                spec = PurgeRelationSpec(
                    _label(field.model),
                    field.name,
                    _label(related_target),
                    kind,
                    through,
                    through_field_name,
                )
            elif getattr(field, "auto_created", False) and not getattr(field, "concrete", False):
                source = getattr(field, "related_model", None)
                source_field = getattr(getattr(field, "field", None), "name", None)
                if source is None or source_field is None:
                    continue
                related_target = getattr(getattr(field, "field", None), "remote_field", None)
                related_target = getattr(related_target, "model", None)
                if related_target not in targets.values():
                    continue
                kind = "many_to_many" if getattr(field, "many_to_many", False) else (
                    "one_to_one" if getattr(field, "one_to_one", False) else "foreign_key"
                )
                through = _label(field.field.remote_field.through) if kind == "many_to_many" else None
                through_field_name = getattr(field.field, "name", None) if kind == "many_to_many" else None
                spec = PurgeRelationSpec(
                    _label(source), source_field, _label(related_target), kind, through, through_field_name
                )
            else:
                continue
            key = (
                spec.source_label,
                spec.field_name,
                spec.target_label,
                spec.kind,
                spec.through_label,
                spec.through_field_name,
            )
            observations[key] = spec
    return tuple(observations.values())


def _relation_matches(observed: PurgeRelationSpec, declared: PurgeRelationSpec) -> bool:
    return (
        observed.source_label == declared.source_label
        and observed.field_name == declared.field_name
        and observed.target_label == declared.target_label
        and observed.kind == declared.kind
        and observed.through_label == declared.through_label
        and observed.through_field_name == declared.through_field_name
    )


def _discover_generic_fields() -> tuple[PurgeGenericReferenceSpec, ...]:
    discovered: list[PurgeGenericReferenceSpec] = []
    declared = tuple(PURGE_GENERIC_REFERENCE_SPECS)
    for model in apps.get_models():
        for field in getattr(model._meta, "private_fields", ()):
            if not isinstance(field, GenericForeignKey):
                continue
            found = PurgeGenericReferenceSpec(_label(model), field.ct_field, field.fk_field)
            if not any(
                found.model_label == item.model_label
                and found.content_type_field == item.content_type_field
                and found.object_id_field == item.object_id_field
                for item in declared
            ):
                _fail(
                    "unregistered GenericForeignKey blocks development purge",
                    ErrorCode.UNSUPPORTED_SCHEMA,
                )
            discovered.append(found)
    return tuple(discovered)


def _validate_generic_specs() -> tuple[PurgeGenericReferenceSpec, ...]:
    discovered = list(_discover_generic_fields())
    for spec in PURGE_GENERIC_REFERENCE_SPECS:
        model = _model_for_label(spec.model_label)
        try:
            content_field = model._meta.get_field(spec.content_type_field)
            model._meta.get_field(spec.object_id_field)
        except LookupError as exc:
            _fail("registered ContentType reference fields are not installed", ErrorCode.UNSUPPORTED_SCHEMA)
            raise AssertionError from exc
        if not getattr(content_field, "remote_field", None) or content_field.remote_field.model is not ContentType:
            _fail("registered ContentType field is not a ContentType relation", ErrorCode.UNSUPPORTED_SCHEMA)
        if not any(
            item.model_label == spec.model_label
            and item.content_type_field == spec.content_type_field
            and item.object_id_field == spec.object_id_field
            for item in discovered
        ):
            discovered.append(spec)
    return tuple(sorted(discovered, key=lambda item: (item.model_label, item.content_type_field, item.object_id_field)))


def _qualified_table(model: type) -> str:
    table = model._meta.db_table
    if "." in table:
        return ".".join(connection.ops.quote_name(part) for part in table.split(".", 1))
    return connection.ops.quote_name(table)


def _lock_table(model: type) -> None:
    with connection.cursor() as cursor:
        cursor.execute(f"LOCK TABLE {_qualified_table(model)} IN SHARE ROW EXCLUSIVE MODE")


def _validate_postgres_constraints(observed: tuple[PurgeRelationSpec, ...]) -> None:
    if connection.vendor != "postgresql":
        _fail("development purge requires PostgreSQL", ErrorCode.UNSUPPORTED_SCHEMA)
    target_tables = {Product._meta.db_table, ProductImage._meta.db_table}
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT source_ns.nspname, source_table.relname, constraint_.conname,
                   target_ns.nspname, target_table.relname,
                   source_column.attname, target_column.attname
            FROM pg_constraint constraint_
            JOIN pg_class source_table ON source_table.oid = constraint_.conrelid
            JOIN pg_namespace source_ns ON source_ns.oid = source_table.relnamespace
            JOIN pg_class target_table ON target_table.oid = constraint_.confrelid
            JOIN pg_namespace target_ns ON target_ns.oid = target_table.relnamespace
            JOIN LATERAL unnest(constraint_.conkey) WITH ORDINALITY source_key(attnum, position) ON TRUE
            JOIN LATERAL unnest(constraint_.confkey) WITH ORDINALITY target_key(attnum, position)
              ON target_key.position = source_key.position
            JOIN pg_attribute source_column
              ON source_column.attrelid = source_table.oid
             AND source_column.attnum = source_key.attnum
            JOIN pg_attribute target_column
              ON target_column.attrelid = target_table.oid
             AND target_column.attnum = target_key.attnum
            WHERE constraint_.contype = 'f'
              AND target_ns.nspname = current_schema()
              AND target_table.relname = ANY(%s)
            ORDER BY source_ns.nspname, source_table.relname, constraint_.conname, source_key.position
            """,
            [list(target_tables)],
        )
        rows = cursor.fetchall()
    model_by_table = {model._meta.db_table: model for model in apps.get_models()}
    expected = set()
    for spec in (*PURGE_INTERNAL_DELETE_EDGES, *PURGE_EXTERNAL_RELATION_SPECS):
        source = _model_for_label(spec.through_label if spec.kind == "many_to_many" else spec.source_label)
        target = _model_for_label(spec.target_label)
        try:
            field_name = spec.through_field_name if spec.kind == "many_to_many" else spec.field_name
            source_column = source._meta.get_field(field_name).column
        except LookupError as exc:
            _fail("purge relation field is not installed", ErrorCode.UNSUPPORTED_SCHEMA)
            raise AssertionError from exc
        expected.add((source._meta.db_table, source_column, target._meta.db_table))
    primary_columns = {
        Product._meta.db_table: Product._meta.pk.column,
        ProductImage._meta.db_table: ProductImage._meta.pk.column,
    }
    for _source_schema, source_table, _constraint, _target_schema, target_table, source_column, target_column in rows:
        source_model = model_by_table.get(source_table)
        if (
            source_model is None
            or (source_table, source_column, target_table) not in expected
            or target_column != primary_columns.get(target_table, target_column)
        ):
            _fail("inbound PostgreSQL constraint is not reviewed for purge", ErrorCode.UNSUPPORTED_SCHEMA)


def _discover_graph() -> _PurgeGraph:
    observed = _relation_observations()
    internal = tuple(PURGE_INTERNAL_DELETE_EDGES)
    external = tuple(PURGE_EXTERNAL_RELATION_SPECS)
    for relation in observed:
        reviewed = any(_relation_matches(relation, item) for item in (*internal, *external))
        if not reviewed:
            _fail(
                f"unregistered relation {relation.source_label}.{relation.field_name}",
                ErrorCode.UNSUPPORTED_SCHEMA,
            )
        source = _model_for_label(relation.source_label)
        try:
            field_name = relation.through_field_name if relation.kind == "many_to_many" else relation.field_name
            relation_field = source._meta.get_field(field_name)
        except LookupError as exc:
            _fail("purge relation field is not installed", ErrorCode.UNSUPPORTED_SCHEMA)
            raise AssertionError from exc
        if relation.kind != "many_to_many" and getattr(relation_field.remote_field, "on_delete", None) not in {
            CASCADE,
            DO_NOTHING,
            PROTECT,
            RESTRICT,
            SET_DEFAULT,
            SET_NULL,
        }:
            _fail("purge relation uses an unreviewed on-delete policy", ErrorCode.UNSUPPORTED_SCHEMA)
    generic = _validate_generic_specs()
    custom = tuple(sorted(PURGE_CUSTOM_INSPECTORS.items(), key=lambda item: item[0]))
    for name, inspector in custom:
        if not callable(inspector):
            _fail(f"purge inspector is not callable: {name}", ErrorCode.UNSUPPORTED_SCHEMA)
    _validate_postgres_constraints(observed)
    lock_models = []
    for spec in (*external, *generic):
        model = _model_for_label(spec.source_label if isinstance(spec, PurgeRelationSpec) else spec.model_label)
        if model not in (Product, ProductImage) and model not in lock_models:
            lock_models.append(model)
        if isinstance(spec, PurgeRelationSpec) and spec.through_label:
            through = _model_for_label(spec.through_label)
            if through not in lock_models:
                lock_models.append(through)
    return _PurgeGraph(external, generic, custom, tuple(sorted(lock_models, key=lambda model: model._meta.label)))


def _active_organization(organization_id: int):
    try:
        return get_active_organization(organization_id)
    except CatalogScopeError as exc:
        _fail(str(exc))


def _candidate_ids(organization_id: int) -> tuple[list[int], list[int]]:
    products = list(Product.objects.filter(organization_id=organization_id).values_list("pk", flat=True))
    images = list(ProductImage.objects.filter(product_id__in=products).values_list("pk", flat=True))
    return products, images


def _blockers_for_graph(graph: _PurgeGraph, product_ids: list[int], image_ids: list[int]) -> list[PurgeBlocker]:
    blockers: list[PurgeBlocker] = []
    target_ids = {
        _label(Product): product_ids,
        _label(ProductImage): image_ids,
    }
    for spec in graph.external:
        model = _model_for_label(spec.source_label)
        target_model = _model_for_label(spec.target_label)
        ids = target_ids[_label(target_model)]
        if spec.kind == "many_to_many":
            if not spec.through_label:
                _fail("many-to-many purge relation has no through model", ErrorCode.UNSUPPORTED_SCHEMA)
            model = _model_for_label(spec.through_label)
            field_name = spec.through_field_name
        else:
            field_name = spec.field_name
        if ids:
            if not field_name:
                _fail("purge relation has no scan field", ErrorCode.UNSUPPORTED_SCHEMA)
            rows = model.objects.filter(**{f"{field_name}__in": ids}).values_list("pk", flat=True)
        else:
            rows = model.objects.none().values_list("pk", flat=True)
        for pk in rows.iterator():
            blockers.append(PurgeBlocker(
                ErrorCode.REFERENCED_CATALOG,
                f"{spec.source_label}.{field_name}:{pk}",
                "reviewed relation references a purge candidate",
            ))
    for spec in graph.generic:
        model = _model_for_label(spec.model_label)
        content_types = [
            ContentType.objects.get_for_model(Product, for_concrete_model=False),
            ContentType.objects.get_for_model(ProductImage, for_concrete_model=False),
        ]
        for content_type in content_types:
            ids = target_ids[_label(Product if content_type.model == Product._meta.model_name else ProductImage)]
            if not ids:
                continue
            query = model.objects.filter(
                **{
                    f"{spec.content_type_field}_id": content_type.pk,
                    f"{spec.object_id_field}__in": [str(value) for value in ids],
                }
            )
            for pk in query.values_list("pk", flat=True).iterator():
                blockers.append(PurgeBlocker(
                    ErrorCode.REFERENCED_CATALOG,
                    f"{spec.model_label}.{spec.object_id_field}:{pk}",
                    "registered ContentType reference points to a purge candidate",
                ))
    for name, inspector in graph.custom:
        result = inspector(tuple(product_ids), tuple(image_ids))
        if not isinstance(result, (list, tuple)):
            _fail(f"purge inspector returned an incomplete result: {name}", ErrorCode.UNSUPPORTED_SCHEMA)
        for item in result:
            if not isinstance(item, PurgeBlocker):
                _fail(f"purge inspector returned an invalid blocker: {name}", ErrorCode.UNSUPPORTED_SCHEMA)
            blockers.append(item)
    return sorted(blockers, key=lambda item: (item.identity, item.code.value, item.message))


def _inspect_collector(products: list[Product], images: list[ProductImage]) -> None:
    collector = Collector(using="default")
    # Related objects are already classified and candidate images are deleted first;
    # collect_related=False lets the assertion inspect exactly the proposed rows.
    collector.collect(images, collect_related=False)
    collector.collect(products, collect_related=False)
    allowed = {Product: {row.pk for row in products}, ProductImage: {row.pk for row in images}}
    for model, rows in collector.data.items():
        if model not in allowed or {row.pk for row in rows} != allowed[model]:
            _fail("Django deletion collector found an unreviewed row", ErrorCode.UNSUPPORTED_SCHEMA)
    for queryset in collector.fast_deletes:
        model = queryset.model
        if model not in allowed or set(queryset.values_list("pk", flat=True)) - allowed[model]:
            _fail("Django deletion collector found an unreviewed fast delete", ErrorCode.UNSUPPORTED_SCHEMA)
    if (
        collector.field_updates
        or collector.restricted_objects
        or getattr(collector, "protected", ())
    ):
        _fail("Django deletion collector found an external effect", ErrorCode.UNSUPPORTED_SCHEMA)


def _prepared_media(snapshot) -> dict[str, Any]:
    images = {(image["product_portable_id"], image["portable_id"]): image for image in snapshot.images}
    return {
        storage_key: type("Prepared", (), {
            "asset_path": images[(product_id, image_id)]["asset_path"],
            "sha256": images[(product_id, image_id)]["content_sha256"],
        })()
        for product_id, image_id, storage_key in snapshot.image_storage_keys
    }


def _bounded(blockers: list[PurgeBlocker]) -> tuple[tuple[PurgeBlocker, ...], int, bool]:
    return tuple(blockers[:MAX_BLOCKERS]), len(blockers), len(blockers) > MAX_BLOCKERS


def preview_catalog_dev_purge(organization_id: int, *, storage_adapter=None) -> PurgePreview:
    _require_development_purge()
    organization = _active_organization(organization_id)
    graph = _discover_graph()
    snapshot = _target_snapshot(organization.pk, storage_adapter)
    product_ids, image_ids = _candidate_ids(organization.pk)
    blockers, total, truncated = _bounded(_blockers_for_graph(graph, product_ids, image_ids))
    return PurgePreview(
        organization_id=organization.pk,
        target_digest=snapshot.digest,
        product_count=len(product_ids),
        product_image_count=len(image_ids),
        valid=not blockers and total == 0,
        blockers=blockers,
        total_blocker_count=total,
        blockers_truncated=truncated,
    )


def _raise_blockers(blockers: list[PurgeBlocker]) -> None:
    if blockers:
        blocker = blockers[0]
        raise CatalogPackageError(blocker.code, blocker.message, path=blocker.identity)


def apply_catalog_dev_purge(
    organization_id: int,
    *,
    operation_id: uuid.UUID,
    expected_catalog_digest: str,
    confirm_purge: str,
    storage_adapter=None,
):
    _require_development_purge()
    _validate_inputs(organization_id, operation_id, expected_catalog_digest, confirm_purge)
    fingerprint = _fingerprint(organization_id, expected_catalog_digest, confirm_purge)
    existing = find_operation_receipt(operation_id, input_fingerprint=fingerprint)
    if existing is not None:
        return existing
    organization = _active_organization(organization_id)
    preflight = _target_snapshot(organization.pk, storage_adapter)
    if preflight.digest != expected_catalog_digest:
        _fail("target catalog changed since purge preview", ErrorCode.STALE_TARGET)
    preflight_rows = _capture_target_rows(organization.pk)
    preflight_token = _target_state_token(preflight_rows[0], preflight_rows[1])
    prepared_media = _prepared_media(preflight)
    try:
        with catalog_write_lock(organization.pk) as locked_organization:
            _require_development_purge()
            if locked_organization.status != Organization.STATUS_ACTIVE:
                _fail("purge requires an active Organization")
            locked_receipt = find_operation_receipt(operation_id, input_fingerprint=fingerprint)
            if locked_receipt is not None:
                return locked_receipt
            _lock_table(Product)
            _lock_table(ProductImage)
            graph = _discover_graph()
            for model in graph.lock_models:
                _lock_table(model)
            locked_rows = _capture_target_rows_locked(organization.pk)
            if _target_state_token(locked_rows[0], locked_rows[1]) != preflight_token:
                _fail("target catalog changed during purge preparation", ErrorCode.STALE_TARGET)
            locked_target = _target_snapshot_from_rows(*locked_rows, prepared_media)
            if locked_target.digest != expected_catalog_digest:
                _fail("target catalog digest changed during purge preparation", ErrorCode.STALE_TARGET)
            product_ids, image_ids = _candidate_ids(organization.pk)
            _raise_blockers(_blockers_for_graph(graph, product_ids, image_ids))
            products = list(Product.objects.filter(pk__in=product_ids).order_by("pk"))
            images = list(ProductImage.objects.filter(pk__in=image_ids).order_by("pk"))
            _inspect_collector(products, images)
            old_receipts = set(CatalogOperationReceipt.objects.filter(organization_id=organization.pk).values_list("pk", flat=True))
            image_deleted, image_details = ProductImage.objects.filter(pk__in=image_ids).delete()
            if image_deleted != len(image_ids) or set(image_details) - {"catalog.ProductImage"}:
                _fail("ProductImage deletion exceeded the reviewed allowlist", ErrorCode.UNSUPPORTED_SCHEMA)
            product_deleted, product_details = Product.objects.filter(pk__in=product_ids).delete()
            if product_deleted != len(product_ids) or set(product_details) - {"catalog.Product"}:
                _fail("Product deletion exceeded the reviewed allowlist", ErrorCode.UNSUPPORTED_SCHEMA)
            if Product.objects.filter(pk__in=product_ids).exists() or ProductImage.objects.filter(pk__in=image_ids).exists():
                _fail("purge candidates remain after deletion", ErrorCode.IMPORT_FAILED)
            if set(CatalogOperationReceipt.objects.filter(organization_id=organization.pk).values_list("pk", flat=True)) != old_receipts:
                _fail("existing operation receipts changed during purge", ErrorCode.IMPORT_FAILED)
            empty = _target_snapshot_from_rows([], [], [], {})
            receipt = create_operation_receipt(
                operation_id=operation_id,
                organization_id=organization.pk,
                operation_type=OPERATION_TYPE,
                input_fingerprint=fingerprint,
                expected_catalog_digest=expected_catalog_digest,
                pre_catalog_digest=expected_catalog_digest,
                post_catalog_digest=empty.digest,
                result_counts={"products_deleted": len(product_ids), "product_images_deleted": len(image_ids)},
            )
        return receipt
    except (CatalogPackageError, CatalogBusyError):
        raise
    except Exception as exc:
        try:
            resolved = find_operation_receipt(operation_id, input_fingerprint=fingerprint)
        except Exception as resolution_exc:
            raise CatalogPackageError(ErrorCode.OUTCOME_UNKNOWN, "purge outcome could not be established") from resolution_exc
        if resolved is not None:
            return resolved
        raise CatalogPackageError(ErrorCode.IMPORT_FAILED, "development catalog purge failed") from exc


purge_catalog = apply_catalog_dev_purge
