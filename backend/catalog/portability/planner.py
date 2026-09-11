"""Pure target reconciliation and preview planning for Catalog Portability v1."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from django.conf import settings

from catalog.media import read_product_image, verify_package_images
from catalog.models import Product, ProductImage
from catalog.portability.codec import CatalogPackage, canonical_json_bytes, decode_package
from catalog.portability.compatibility import (
    inventory_protections_active,
    require_compatible_catalog,
)
from catalog.portability.errors import CatalogPackageError
from catalog.portability.schema import (
    ErrorCode,
    MAX_IMAGE_BYTES,
    ZIP_FILE_LIMIT_BYTES,
    validate_catalog,
    validate_manifest,
)
from catalog.services import catalog_write_lock, get_active_organization
from media_storage.configuration import get_media_storage
from media_storage.errors import MediaError
from organizations.models import Organization


MODES = frozenset({"merge", "replace-storefront"})
INVENTORY_POLICIES = frozenset({"preserve", "restore-snapshot"})
MAX_DISPLAYED_ERRORS = 100


@dataclass(frozen=True)
class PlanError:
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
class PlanAction:
    kind: str
    identity: str
    product_portable_id: str
    image_portable_id: str | None = None
    changes: dict[str, Any] | None = None
    incoming_stock_quantity: int | None = None
    stock_preserved: bool = False

    def as_dict(self) -> dict[str, Any]:
        result = {
            "kind": self.kind,
            "identity": self.identity,
            "product_portable_id": self.product_portable_id,
            "image_portable_id": self.image_portable_id,
            "changes": self.changes or {},
            "incoming_stock_quantity": self.incoming_stock_quantity,
            "stock_preserved": self.stock_preserved,
        }
        return result


@dataclass(frozen=True)
class CatalogPlan:
    organization_id: int
    mode: str
    inventory_policy: str
    package_sha256: str
    target_digest: str
    actions: tuple[PlanAction, ...]
    counts: dict[str, int]
    errors: tuple[PlanError, ...] = ()
    total_error_count: int = 0
    errors_truncated: bool = False

    @property
    def valid(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        return {
            "organization_id": self.organization_id,
            "mode": self.mode,
            "inventory_policy": self.inventory_policy,
            "package_sha256": self.package_sha256,
            "target_digest": self.target_digest,
            "actions": [action.as_dict() for action in self.actions],
            "counts": self.counts,
            "errors": [error.as_dict() for error in self.errors],
            "total_error_count": self.total_error_count,
            "errors_truncated": self.errors_truncated,
        }


@dataclass(frozen=True)
class _TargetSnapshot:
    products: tuple[dict[str, Any], ...]
    images: tuple[dict[str, Any], ...]
    image_storage_keys: tuple[tuple[str, str, str], ...]
    digest: str


def _error(code: ErrorCode, identity: str, message: str) -> PlanError:
    return PlanError(code, identity, message)


def _bounded_errors(errors: list[PlanError]) -> tuple[tuple[PlanError, ...], int, bool]:
    ordered = sorted(errors, key=lambda item: (item.identity, item.code.value, item.message))
    return (
        tuple(ordered[:MAX_DISPLAYED_ERRORS]),
        len(ordered),
        len(ordered) > MAX_DISPLAYED_ERRORS,
    )


def _product_snapshot(product: Product) -> dict[str, Any]:
    return {
        "portable_id": str(product.portable_id),
        "sku": product.sku,
        "name": product.name,
        "description": product.description,
        "price": format(product.price, ".2f"),
        "stock_quantity": product.stock_quantity,
        "status": "active" if product.is_active else "inactive",
    }


def _capture_target_rows_locked(
    organization_id: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[tuple[str, str, str]]]:
    """Capture rows while the caller owns the Organization lock."""
    products = list(
        Product.objects.filter(organization_id=organization_id).order_by("portable_id")
    )
    for product in products:
        if product.product_type != "physical":
            raise CatalogPackageError(
                ErrorCode.UNSUPPORTED_SCHEMA,
                "target contains an unsupported service Product",
                path=f"products[{product.portable_id}].product_type",
            )
    product_ids = {product.pk: str(product.portable_id) for product in products}
    images = list(
        ProductImage.objects.filter(product__organization_id=organization_id)
        .select_related("product")
        .order_by("product__portable_id", "sort_order", "portable_id")
    )
    product_rows = [_product_snapshot(product) for product in products]
    image_rows = []
    storage_keys = []
    for image in images:
        product_portable_id = product_ids.get(image.product_id)
        if product_portable_id is None:
            raise CatalogPackageError(
                ErrorCode.UNSUPPORTED_SCHEMA,
                "target ProductImage is outside the selected Organization",
            )
        image_rows.append(
            {
                "portable_id": str(image.portable_id),
                "product_portable_id": product_portable_id,
                "alt_text": image.alt_text,
                "sort_order": image.sort_order,
                "is_primary": image.is_primary,
                "storage_key": image.storage_key,
            }
        )
        storage_keys.append((product_portable_id, str(image.portable_id), image.storage_key))
    return product_rows, image_rows, storage_keys


def _capture_target_rows(
    organization_id: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[tuple[str, str, str]]]:
    with catalog_write_lock(organization_id) as organization:
        if organization.status != Organization.STATUS_ACTIVE:
            raise CatalogPackageError(
                ErrorCode.OPERATION_NOT_ALLOWED,
                "planning requires an active Organization",
            )
        return _capture_target_rows_locked(organization_id)


def _target_snapshot_from_rows(
    product_rows: list[dict[str, Any]],
    image_rows: list[dict[str, Any]],
    storage_keys: list[tuple[str, str]],
    prepared_by_storage_key: dict[str, Any],
) -> _TargetSnapshot:
    prepared_images = []
    for image in image_rows:
        prepared = prepared_by_storage_key.get(image["storage_key"])
        if prepared is None:
            raise CatalogPackageError(
                ErrorCode.MEDIA_UNAVAILABLE,
                "target ProductImage media could not be verified",
                path=f"target.product_images[{image['portable_id']}]",
            )
        image_copy = dict(image)
        image_copy.pop("storage_key")
        image_copy["asset_path"] = prepared.asset_path
        image_copy["content_sha256"] = prepared.sha256
        prepared_images.append(image_copy)
    digest_value = {"products": product_rows, "product_images": prepared_images}
    digest = hashlib.sha256(canonical_json_bytes(digest_value)).hexdigest()
    return _TargetSnapshot(tuple(product_rows), tuple(prepared_images), tuple(storage_keys), digest)


def _target_state_token(
    product_rows: list[dict[str, Any]],
    image_rows: list[dict[str, Any]],
) -> str:
    return hashlib.sha256(canonical_json_bytes({
        "products": product_rows,
        "product_images": image_rows,
    })).hexdigest()


def _target_snapshot(organization_id: int, storage_adapter=None) -> _TargetSnapshot:
    product_rows, image_rows, storage_keys = _capture_target_rows(organization_id)
    if storage_keys and storage_adapter is None:
        storage_adapter = get_media_storage()

    prepared_by_storage_key = {}
    for index, image in enumerate(image_rows):
        try:
            stored, prepared = read_product_image(
                storage_adapter,
                image["storage_key"],
                MAX_IMAGE_BYTES,
            )
            if stored.sha256 != prepared.sha256 or stored.content != prepared.content:
                raise MediaError(
                    ErrorCode.MEDIA_UNAVAILABLE,
                    "target media readback metadata is inconsistent",
                )
        except MediaError as exc:
            raise CatalogPackageError(
                ErrorCode.MEDIA_UNAVAILABLE,
                "target ProductImage media could not be verified",
                path=f"target.product_images[{index}]",
            ) from exc
        prepared_by_storage_key[image["storage_key"]] = prepared
    return _target_snapshot_from_rows(product_rows, image_rows, storage_keys, prepared_by_storage_key)


def build_locked_target_snapshot(
    organization_id: int,
    *,
    prepared_by_storage_key: dict[str, Any],
) -> tuple[_TargetSnapshot, str]:
    """Build a target snapshot without acquiring a lock or reading storage."""
    rows = _capture_target_rows_locked(organization_id)
    return _target_snapshot_from_rows(*rows, prepared_by_storage_key), _target_state_token(rows[0], rows[1])


def validate_inventory_policy(inventory_policy: str) -> None:
    if inventory_policy not in INVENTORY_POLICIES:
        raise CatalogPackageError(ErrorCode.OPERATION_NOT_ALLOWED, "invalid inventory policy")
    if inventory_policy == "restore-snapshot":
        if getattr(settings, "COMMERCE_ENV", "") != "development":
            raise CatalogPackageError(ErrorCode.OPERATION_NOT_ALLOWED, "snapshot stock restore is development-only")
        if not getattr(settings, "CATALOG_ALLOW_SNAPSHOT_STOCK_RESTORE", False):
            raise CatalogPackageError(ErrorCode.OPERATION_NOT_ALLOWED, "snapshot stock restore is disabled")
        if inventory_protections_active():
            raise CatalogPackageError(ErrorCode.OPERATION_NOT_ALLOWED, "active inventory protection forbids snapshot restore")


def compute_target_digest(organization_id, *, storage_adapter=None) -> str:
    """Return the stable digest of one current Organization catalog snapshot."""

    organization = get_active_organization(organization_id)
    require_compatible_catalog()
    return _target_snapshot(organization.pk, storage_adapter).digest


def _package_parts(package, package_sha256: str | None):
    if isinstance(package, CatalogPackage):
        validate_manifest(package.manifest)
        validate_catalog(package.catalog)
        from catalog.portability.codec import encode_package

        encoded = encode_package(package.manifest, package.catalog, package.media)
        raw_package_sha256 = package_sha256 or hashlib.sha256(encoded).hexdigest()
        return package, raw_package_sha256
    if isinstance(package, dict) and {"manifest", "catalog", "media"} <= set(package):
        return _package_parts(
            CatalogPackage(package["manifest"], package["catalog"], package["media"]),
            package_sha256,
        )
    if isinstance(package, (bytes, bytearray, memoryview)):
        raw = bytes(package)
    elif hasattr(package, "read"):
        if hasattr(package, "seek"):
            package.seek(0)
            digest = hashlib.sha256()
            total = 0
            while True:
                chunk = package.read(min(1024 * 1024, ZIP_FILE_LIMIT_BYTES + 1 - total))
                if not chunk:
                    break
                total += len(chunk)
                if total > ZIP_FILE_LIMIT_BYTES:
                    raise CatalogPackageError(ErrorCode.LIMIT_EXCEEDED, "ZIP file limit exceeded")
                digest.update(chunk)
            package.seek(0)
            return decode_package(package), digest.hexdigest()
        chunks = []
        total = 0
        while True:
            chunk = package.read(min(1024 * 1024, ZIP_FILE_LIMIT_BYTES + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            if total > ZIP_FILE_LIMIT_BYTES:
                raise CatalogPackageError(ErrorCode.LIMIT_EXCEEDED, "ZIP file limit exceeded")
            chunks.append(chunk)
        raw = b"".join(chunks)
    else:
        raise CatalogPackageError(
            ErrorCode.INVALID_PACKAGE,
            "planner input must be a CatalogPackage, ZIP bytes, or readable stream",
        )
    decoded = decode_package(raw)
    return decoded, hashlib.sha256(raw).hexdigest()


def _validate_package_images(package: CatalogPackage) -> None:
    try:
        verify_package_images(package)
    except MediaError as exc:
        raise CatalogPackageError(exc.code, "package image could not be verified") from exc


def _product_changes(target: dict[str, Any], incoming: dict[str, Any], inventory_policy: str):
    changes = {}
    for field in ("sku", "name", "description", "price", "status"):
        if target[field] != incoming[field]:
            changes[field] = incoming[field]
    incoming_stock = incoming["stock_quantity"]
    stock_preserved = inventory_policy == "preserve"
    if inventory_policy == "restore-snapshot" and target["stock_quantity"] != incoming_stock:
        changes["stock_quantity"] = incoming_stock
    return changes, incoming_stock, stock_preserved


def _image_changes(target: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    changes = {}
    for field in (
        "asset_path",
        "alt_text",
        "sort_order",
        "is_primary",
    ):
        if target[field] != incoming[field]:
            changes[field] = incoming[field]
    return changes


def _make_plan(
    organization_id: int,
    package: CatalogPackage,
    package_sha256: str,
    target: _TargetSnapshot,
    mode: str,
    inventory_policy: str,
    initial_errors: list[PlanError],
) -> CatalogPlan:
    errors = list(initial_errors)
    incoming_products = package.catalog["products"]
    incoming_images = package.catalog["product_images"]
    target_by_id = {row["portable_id"]: row for row in target.products}
    target_by_sku = {row["sku"]: row["portable_id"] for row in target.products}
    incoming_by_id = {row["portable_id"]: row for row in incoming_products}
    incoming_sku_owner: dict[str, str] = {}
    for index, product in enumerate(incoming_products):
        owner = incoming_sku_owner.get(product["sku"])
        if owner is not None and owner != product["portable_id"]:
            errors.append(
                _error(
                    ErrorCode.DUPLICATE_SKU,
                    f"products[{index}].sku",
                    "duplicate Product SKU inside package",
                )
            )
        incoming_sku_owner[product["sku"]] = product["portable_id"]

    actions: list[PlanAction] = []
    for index, incoming in enumerate(incoming_products):
        identity = incoming["portable_id"]
        target_product = target_by_id.get(identity)
        sku_owner = target_by_sku.get(incoming["sku"])
        if sku_owner is not None and sku_owner != identity:
            errors.append(
                _error(
                    ErrorCode.SKU_CONFLICT,
                    f"products[{index}].sku",
                    "incoming SKU belongs to another target Product",
                )
            )
        if target_product is None:
            create_changes = dict(incoming)
            if inventory_policy == "preserve":
                create_changes["stock_quantity"] = 0
            actions.append(
                PlanAction(
                    "create",
                    identity,
                    identity,
                    changes=create_changes,
                    incoming_stock_quantity=incoming["stock_quantity"],
                )
            )
        else:
            changes, incoming_stock, stock_preserved = _product_changes(
                target_product,
                incoming,
                inventory_policy,
            )
            actions.append(
                PlanAction(
                    "update" if changes else "no-op",
                    identity,
                    identity,
                    changes=changes,
                    incoming_stock_quantity=incoming_stock,
                    stock_preserved=stock_preserved,
                )
            )

    target_images = {
        (image["product_portable_id"], image["portable_id"]): image
        for image in target.images
    }
    target_images_by_product: dict[str, list[dict[str, Any]]] = {}
    for image in target.images:
        target_images_by_product.setdefault(image["product_portable_id"], []).append(image)
    incoming_images_by_product: dict[str, list[dict[str, Any]]] = {}
    for image in incoming_images:
        incoming_images_by_product.setdefault(image["product_portable_id"], []).append(image)
        key = (image["product_portable_id"], image["portable_id"])
        target_image = target_images.get(key)
        if target_image is None:
            actions.append(
                PlanAction(
                    "create-image",
                    f"{image['product_portable_id']}/{image['portable_id']}",
                    image["product_portable_id"],
                    image_portable_id=image["portable_id"],
                    changes=dict(image),
                )
            )
        else:
            changes = _image_changes(target_image, image)
            actions.append(
                PlanAction(
                    "update-image" if changes else "no-op-image",
                    f"{image['product_portable_id']}/{image['portable_id']}",
                    image["product_portable_id"],
                    image_portable_id=image["portable_id"],
                    changes=changes,
                )
            )

    if mode in {"merge", "replace-storefront"}:
        for target_product in target.products:
            product_id = target_product["portable_id"]
            if product_id not in incoming_by_id:
                if mode == "replace-storefront" and target_product["status"] == "active":
                    actions.append(
                        PlanAction("deactivate", product_id, product_id, changes={"status": "inactive"})
                    )
                continue
            incoming_ids = {
                image["portable_id"]
                for image in incoming_images_by_product.get(product_id, [])
            }
            for target_image in target_images_by_product.get(product_id, []):
                if (
                    target_image["product_portable_id"] == product_id
                    and target_image["portable_id"] not in incoming_ids
                ):
                    image_id = target_image["portable_id"]
                    actions.append(
                        PlanAction(
                            "remove-image",
                            f"{product_id}/{image_id}",
                            product_id,
                            image_portable_id=image_id,
                        )
                    )

    if errors:
        actions = []
    actions.sort(key=lambda action: (action.product_portable_id, action.image_portable_id or "", action.kind))
    bounded, total, truncated = _bounded_errors(errors)
    counts = {
        "creates": sum(action.kind in {"create", "create-image"} for action in actions),
        "updates": sum(action.kind in {"update", "update-image"} for action in actions),
        "no_ops": sum(action.kind in {"no-op", "no-op-image"} for action in actions),
        "removals": sum(action.kind == "remove-image" for action in actions),
        "deactivations": sum(action.kind == "deactivate" for action in actions),
    }
    return CatalogPlan(
        organization_id,
        mode,
        inventory_policy,
        package_sha256,
        target.digest,
        tuple(actions),
        counts,
        bounded,
        total,
        truncated,
    )


def plan_catalog_import(
    package,
    organization_id,
    *,
    mode: str,
    inventory_policy: str = "preserve",
    storage_adapter=None,
    package_sha256: str | None = None,
) -> CatalogPlan:
    """Build a mutation-free reconciliation plan for one target Organization."""

    if mode not in MODES:
        raise CatalogPackageError(ErrorCode.OPERATION_NOT_ALLOWED, "mode must be merge or replace-storefront")
    validate_inventory_policy(inventory_policy)
    require_compatible_catalog()
    organization = get_active_organization(organization_id)
    package_object, fingerprint = _package_parts(package, package_sha256)
    _validate_package_images(package_object)
    target = _target_snapshot(organization.pk, storage_adapter)
    return _make_plan(
        organization.pk,
        package_object,
        fingerprint,
        target,
        mode,
        inventory_policy,
        [],
    )


build_import_plan = plan_catalog_import
