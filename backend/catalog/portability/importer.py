"""Atomic application of a validated Catalog Portability package."""

from __future__ import annotations

import hashlib
import uuid
from types import SimpleNamespace
from typing import Literal

from django.db import IntegrityError
from django.utils import timezone

from catalog.media import store_verified_product_image, verify_package_images
from catalog.models import Product, ProductImage
from catalog.portability.codec import decode_package
from catalog.portability.errors import CatalogPackageError
from catalog.portability.planner import (
    MODES,
    ZIP_FILE_LIMIT_BYTES,
    _capture_target_rows,
    _capture_target_rows_locked,
    _make_plan,
    _target_snapshot,
    _target_snapshot_from_rows,
    _target_state_token,
    plan_catalog_import,
    validate_inventory_policy,
)
from catalog.portability.receipts import (
    create_operation_receipt,
    find_operation_receipt,
    operation_input_fingerprint,
)
from catalog.portability.schema import ErrorCode, SHA256_PATTERN
from catalog.services import CatalogBusyError, catalog_write_lock
from media_storage.configuration import get_media_storage
from organizations.models import Organization


OPERATION_TYPE = "catalog-import"


def _fail(code: ErrorCode, message: str) -> None:
    raise CatalogPackageError(code, message)


def _validate_inputs(
    package_bytes: bytes,
    organization_id: int,
    mode: str,
    inventory_policy: str,
    operation_id: uuid.UUID,
    expected_package_sha256: str,
    expected_catalog_digest: str,
    confirmed_organization_id: int | None,
) -> None:
    if not isinstance(package_bytes, bytes):
        _fail(ErrorCode.INVALID_PACKAGE, "package_bytes must be immutable bytes")
    if len(package_bytes) > ZIP_FILE_LIMIT_BYTES:
        _fail(ErrorCode.LIMIT_EXCEEDED, "ZIP file limit exceeded")
    if isinstance(organization_id, bool) or not isinstance(organization_id, int) or organization_id <= 0:
        _fail(ErrorCode.OPERATION_NOT_ALLOWED, "a positive Organization ID is required")
    if mode not in MODES:
        _fail(ErrorCode.OPERATION_NOT_ALLOWED, "mode must be merge or replace-storefront")
    validate_inventory_policy(inventory_policy)
    if not isinstance(operation_id, uuid.UUID) or operation_id.version != 4:
        _fail(ErrorCode.OPERATION_NOT_ALLOWED, "operation_id must be a UUIDv4")
    for value, label in (
        (expected_package_sha256, "expected_package_sha256"),
        (expected_catalog_digest, "expected_catalog_digest"),
    ):
        if not isinstance(value, str) or not SHA256_PATTERN.fullmatch(value):
            _fail(ErrorCode.OPERATION_NOT_ALLOWED, f"{label} must be a canonical lowercase SHA-256")
    if confirmed_organization_id is not None and (
        isinstance(confirmed_organization_id, bool)
        or not isinstance(confirmed_organization_id, int)
        or confirmed_organization_id <= 0
    ):
        _fail(ErrorCode.OPERATION_NOT_ALLOWED, "confirmed Organization ID must be positive")
    if mode == "replace-storefront" and confirmed_organization_id != organization_id:
        _fail(ErrorCode.OPERATION_NOT_ALLOWED, "replace-storefront requires Organization confirmation")
    if mode == "merge" and confirmed_organization_id is not None:
        _fail(ErrorCode.OPERATION_NOT_ALLOWED, "Organization confirmation is only valid for replace-storefront")


def _stage_media(package, storage_adapter):
    prepared = verify_package_images(package)
    stored = {}
    for path in sorted(prepared):
        image = prepared[path]
        try:
            result = store_verified_product_image(storage_adapter, image)
            matches = (
                result.sha256 == image.sha256
                and result.size_bytes == image.size_bytes
                and result.content_type == image.content_type
                and result.storage_key == f"sha256/{image.sha256}"
            )
        except Exception as exc:
            raise CatalogPackageError(ErrorCode.MEDIA_UNAVAILABLE, "package image could not be staged", path=path) from exc
        if not matches:
            raise CatalogPackageError(ErrorCode.MEDIA_UNAVAILABLE, "staged image does not match verified content", path=path)
        stored[path] = result
    return prepared, stored


def _media_index(target, prepared, stored):
    result = {}
    for image in target.images:
        descriptor = SimpleNamespace(
            asset_path=image["asset_path"],
            sha256=image["content_sha256"],
        )
        result[dict(target.image_storage_keys).get(image["portable_id"], "")] = descriptor
    for path, media in stored.items():
        result[media.storage_key] = prepared[path]
    return result


def _save_product(product, changes):
    effective = {}
    for field, value in changes.items():
        if field == "status":
            value = value == "active"
            field = "is_active"
        if field == "price":
            from decimal import Decimal
            value = Decimal(value)
        if getattr(product, field) != value:
            setattr(product, field, value)
            effective[field] = value
    if effective:
        product.save(update_fields=set(effective) | {"updated_at"})


def _apply_products(package, plan, organization_id):
    products = {
        str(product.portable_id): product
        for product in Product.objects.filter(organization_id=organization_id)
    }
    incoming = {row["portable_id"]: row for row in package.catalog["products"]}
    for action in plan.actions:
        if action.kind not in {"create", "update"} or action.image_portable_id is not None:
            continue
        row = incoming[action.product_portable_id]
        if action.kind == "create":
            changes = dict(action.changes or {})
            from decimal import Decimal
            product = Product(
                organization_id=organization_id,
                portable_id=uuid.UUID(row["portable_id"]),
                sku=changes["sku"],
                name=changes["name"],
                description=changes["description"],
                product_type="physical",
                price=Decimal(changes["price"]),
                is_active=changes["status"] == "active",
                stock_quantity=changes["stock_quantity"],
            )
            product.save()
            products[action.product_portable_id] = product
        else:
            _save_product(products[action.product_portable_id], action.changes or {})
    return products


def _apply_images(package, products, stored_by_path):
    incoming_by_product = {}
    for row in package.catalog["products"]:
        incoming_by_product.setdefault(row["portable_id"], [])
    for row in package.catalog["product_images"]:
        incoming_by_product.setdefault(row["product_portable_id"], []).append(row)
    for product_id in sorted(incoming_by_product):
        product = products[product_id]
        desired = sorted(incoming_by_product[product_id], key=lambda row: row["portable_id"])
        current = {
            str(image.portable_id): image
            for image in ProductImage.objects.filter(product=product)
        }
        final_primary = next((row["portable_id"] for row in desired if row["is_primary"]), None)
        current_primary = next((key for key, image in current.items() if image.is_primary), None)
        if current_primary != final_primary and current_primary in current:
            ProductImage.objects.filter(pk=current[current_primary].pk).update(
                is_primary=False, updated_at=timezone.now()
            )
            current[current_primary].is_primary = False
        for row in desired:
            image = current.get(row["portable_id"])
            keep_primary = row["is_primary"] and current_primary == final_primary
            values = {
                "storage_key": stored_by_path[row["asset_path"]].storage_key,
                "alt_text": row["alt_text"],
                "sort_order": row["sort_order"],
                "is_primary": bool(keep_primary),
            }
            if image is None:
                ProductImage.objects.create(
                    product=product,
                    portable_id=uuid.UUID(row["portable_id"]),
                    **values,
                )
            else:
                changed = False
                for field, value in values.items():
                    if getattr(image, field) != value:
                        setattr(image, field, value)
                        changed = True
                if changed:
                    image.save(update_fields=set(values) | {"updated_at"})
        omitted = set(current) - {row["portable_id"] for row in desired}
        if omitted:
            ProductImage.objects.filter(pk__in=[current[key].pk for key in omitted]).delete()
        if final_primary:
            image = ProductImage.objects.get(product=product, portable_id=final_primary)
            if not image.is_primary:
                ProductImage.objects.filter(pk=image.pk).update(is_primary=True, updated_at=timezone.now())


def _deactivate_destination_only(package, products, organization_id):
    incoming_ids = {row["portable_id"] for row in package.catalog["products"]}
    for product in Product.objects.filter(organization_id=organization_id, is_active=True):
        if str(product.portable_id) not in incoming_ids:
            product.is_active = False
            product.save(update_fields={"is_active", "updated_at"})


def _assert_final_state(package, products, organization_id, mode, inventory_policy, staged):
    """Validate the committed aggregate before the receipt is written."""
    incoming = {row["portable_id"]: row for row in package.catalog["products"]}
    for identity, row in incoming.items():
        product = Product.objects.get(organization_id=organization_id, portable_id=identity)
        expected_stock = row["stock_quantity"] if inventory_policy == "restore-snapshot" else product.stock_quantity
        if (
            product.sku != row["sku"]
            or product.name != row["name"]
            or product.description != row["description"]
            or format(product.price, ".2f") != row["price"]
            or product.is_active != (row["status"] == "active")
            or product.stock_quantity != expected_stock
            or product.product_type != "physical"
        ):
            raise CatalogPackageError(ErrorCode.IMPORT_FAILED, "final Product aggregate differs from the plan")
        actual_images = {
            str(image.portable_id): image
            for image in ProductImage.objects.filter(product=product)
        }
        expected_images = {
            row["portable_id"]: row
            for row in package.catalog["product_images"]
            if row["product_portable_id"] == identity
        }
        if set(actual_images) != set(expected_images):
            raise CatalogPackageError(ErrorCode.IMPORT_FAILED, "final ProductImage set differs from the plan")
        for image_id, image_row in expected_images.items():
            image = actual_images[image_id]
            if (
                image.storage_key != staged[image_row["asset_path"]].storage_key
                or image.alt_text != image_row["alt_text"]
                or image.sort_order != image_row["sort_order"]
                or image.is_primary != image_row["is_primary"]
            ):
                raise CatalogPackageError(ErrorCode.IMPORT_FAILED, "final ProductImage aggregate differs from the plan")
    if mode == "replace-storefront":
        incoming_ids = set(incoming)
        for product in Product.objects.filter(organization_id=organization_id):
            if str(product.portable_id) not in incoming_ids and product.is_active:
                raise CatalogPackageError(ErrorCode.IMPORT_FAILED, "replace-storefront left a destination Product active")


def apply_catalog_import(
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
):
    _validate_inputs(
        package_bytes, organization_id, mode, inventory_policy, operation_id,
        expected_package_sha256, expected_catalog_digest, confirmed_organization_id,
    )
    actual_package_sha256 = hashlib.sha256(package_bytes).hexdigest()
    if actual_package_sha256 != expected_package_sha256:
        _fail(ErrorCode.PACKAGE_CHANGED, "package bytes differ from the preview")
    fingerprint = operation_input_fingerprint(
        organization_id=organization_id,
        operation_type=OPERATION_TYPE,
        mode=mode,
        package_sha256=actual_package_sha256,
        inventory_policy=inventory_policy,
        expected_catalog_digest=expected_catalog_digest,
        confirmation=str(confirmed_organization_id) if confirmed_organization_id is not None else None,
    )
    existing = find_operation_receipt(operation_id, input_fingerprint=fingerprint)
    if existing is not None:
        return existing
    package = decode_package(package_bytes)
    verify_package_images(package)
    if storage_adapter is None:
        storage_adapter = get_media_storage()
    preflight = plan_catalog_import(package_bytes, organization_id, mode=mode, inventory_policy=inventory_policy, storage_adapter=storage_adapter)
    if preflight.target_digest != expected_catalog_digest:
        _fail(ErrorCode.STALE_TARGET, "target catalog changed since preview")
    if not preflight.valid:
        raise CatalogPackageError(preflight.errors[0].code, preflight.errors[0].message, path=preflight.errors[0].identity)
    target = _target_snapshot(organization_id, storage_adapter)
    preflight_rows = _capture_target_rows(organization_id)
    preflight_token = _target_state_token(preflight_rows[0], preflight_rows[1])
    prepared, staged = _stage_media(package, storage_adapter)
    try:
        with catalog_write_lock(organization_id) as organization:
            if organization.status != Organization.STATUS_ACTIVE:
                _fail(ErrorCode.OPERATION_NOT_ALLOWED, "Organization is not active")
            validate_inventory_policy(inventory_policy)
            locked_receipt = find_operation_receipt(operation_id, input_fingerprint=fingerprint)
            if locked_receipt is not None:
                return locked_receipt
            locked_rows = _capture_target_rows_locked(organization_id)
            if _target_state_token(locked_rows[0], locked_rows[1]) != preflight_token:
                _fail(ErrorCode.STALE_TARGET, "target catalog changed during preparation")
            index = _media_index(target, prepared, staged)
            locked_target = _target_snapshot_from_rows(*locked_rows, index)
            if locked_target.digest != expected_catalog_digest:
                _fail(ErrorCode.STALE_TARGET, "target catalog digest changed during preparation")
            plan = _make_plan(organization_id, package, actual_package_sha256, locked_target, mode, inventory_policy, [])
            if not plan.valid:
                raise CatalogPackageError(plan.errors[0].code, plan.errors[0].message, path=plan.errors[0].identity)
            products = _apply_products(package, plan, organization_id)
            _apply_images(package, products, staged)
            if mode == "replace-storefront":
                _deactivate_destination_only(package, products, organization_id)
            _assert_final_state(package, products, organization_id, mode, inventory_policy, staged)
            final_rows = _capture_target_rows_locked(organization_id)
            final_target = _target_snapshot_from_rows(*final_rows, index)
            receipt = create_operation_receipt(
                operation_id=operation_id,
                organization_id=organization_id,
                operation_type=OPERATION_TYPE,
                input_fingerprint=fingerprint,
                package_sha256=actual_package_sha256,
                inventory_policy=inventory_policy,
                expected_catalog_digest=expected_catalog_digest,
                pre_catalog_digest=expected_catalog_digest,
                post_catalog_digest=final_target.digest,
                result_counts=plan.counts,
            )
        return receipt
    except IntegrityError:
        winner = find_operation_receipt(operation_id, input_fingerprint=fingerprint)
        if winner is not None:
            return winner
        _fail(ErrorCode.IMPORT_FAILED, "catalog import transaction failed")
    except (CatalogPackageError, CatalogBusyError):
        raise
    except Exception as exc:
        # A connection/commit acknowledgement can be lost after the database
        # has committed. Resolve by operation ID before declaring failure.
        try:
            resolved = find_operation_receipt(operation_id, input_fingerprint=fingerprint)
        except Exception as resolution_exc:
            raise CatalogPackageError(ErrorCode.OUTCOME_UNKNOWN, "catalog import outcome could not be established") from resolution_exc
        if resolved is not None:
            return resolved
        raise CatalogPackageError(ErrorCode.IMPORT_FAILED, "catalog import transaction failed") from exc
