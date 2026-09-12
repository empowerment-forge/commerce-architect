"""Consistent, Organization-scoped Catalog Portability v1 export."""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

from catalog.media import read_product_image
from catalog.models import Product, ProductImage
from catalog.portability.codec import canonical_json_bytes, encode_package
from catalog.portability.errors import CatalogPackageError
from catalog.portability.schema import (
    CATALOG_MEDIA_TYPE,
    ErrorCode,
    MAX_IMAGE_BYTES,
)
from catalog.services import catalog_write_lock, get_active_organization
from media_storage.configuration import get_media_storage
from media_storage.errors import MediaError
from organizations.models import Organization


def _product_record(product: Product) -> dict:
    return {
        "portable_id": str(product.portable_id),
        "sku": product.sku,
        "name": product.name,
        "description": product.description,
        "price": format(product.price, ".2f"),
        "stock_quantity": product.stock_quantity,
        "status": "active" if product.is_active else "inactive",
    }


def _image_record(image: ProductImage, product_portable_id: str, asset_path: str) -> dict:
    return {
        "portable_id": str(image.portable_id),
        "product_portable_id": product_portable_id,
        "asset_path": asset_path,
        "alt_text": image.alt_text,
        "sort_order": image.sort_order,
        "is_primary": image.is_primary,
    }


def _capture_snapshot(organization_id: int) -> tuple[list[dict], list[dict]]:
    """Copy all scoped rows while the shared Organization lock is held."""

    with catalog_write_lock(organization_id) as organization:
        if organization.status != Organization.STATUS_ACTIVE:
            raise CatalogPackageError(
                ErrorCode.OPERATION_NOT_ALLOWED,
                "export requires an active Organization",
            )
        products = list(
            Product.objects.filter(organization_id=organization_id)
            .order_by("portable_id")
        )
        for product in products:
            if product.product_type != "physical":
                raise CatalogPackageError(
                    ErrorCode.UNSUPPORTED_SCHEMA,
                    "all exported Products must be physical",
                    path=f"products[{product.portable_id}].product_type",
                )

        product_ids = {product.pk: str(product.portable_id) for product in products}
        images = list(
            ProductImage.objects.filter(product__organization_id=organization_id)
            .select_related("product")
            .order_by("product__portable_id", "sort_order", "portable_id")
        )
        product_records = [_product_record(product) for product in products]
        image_snapshots = [
            {
                "image": image,
                "product_portable_id": product_ids.get(image.product_id),
                "storage_key": image.storage_key,
            }
            for image in images
        ]
        if any(snapshot["product_portable_id"] is None for snapshot in image_snapshots):
            raise CatalogPackageError(
                ErrorCode.INVALID_PACKAGE,
                "ProductImage references a Product outside the selected Organization",
            )
        return product_records, image_snapshots


def _build_package(organization_id: int, storage_adapter=None) -> bytes:
    product_records, image_snapshots = _capture_snapshot(organization_id)
    image_records = []
    media: dict[str, bytes] = {}

    if image_snapshots and storage_adapter is None:
        storage_adapter = get_media_storage()

    for index, snapshot in enumerate(image_snapshots):
        image = snapshot["image"]
        try:
            stored, prepared = read_product_image(
                storage_adapter,
                snapshot["storage_key"],
                MAX_IMAGE_BYTES,
            )
            if (
                stored.storage_key != snapshot["storage_key"]
                or stored.sha256 != prepared.sha256
                or stored.size_bytes != prepared.size_bytes
                or stored.content != prepared.content
            ):
                raise MediaError(
                    ErrorCode.MEDIA_UNAVAILABLE,
                    "verified media readback metadata is inconsistent",
                )
        except MediaError as exc:
            raise CatalogPackageError(
                ErrorCode.MEDIA_UNAVAILABLE,
                "referenced ProductImage media could not be verified",
                path=f"product_images[{index}]",
            ) from exc
        except Exception as exc:
            raise CatalogPackageError(
                ErrorCode.MEDIA_UNAVAILABLE,
                "referenced ProductImage media could not be verified",
                path=f"product_images[{index}]",
            ) from exc

        asset_path = prepared.asset_path
        previous = media.get(asset_path)
        if previous is not None and previous != prepared.content:
            raise CatalogPackageError(
                ErrorCode.MEDIA_UNAVAILABLE,
                "one media path resolved to different bytes",
                path=asset_path,
            )
        media[asset_path] = prepared.content
        image_records.append(
            _image_record(image, snapshot["product_portable_id"], asset_path)
        )

    catalog = {
        "products": product_records,
        "product_images": image_records,
    }
    catalog_bytes = canonical_json_bytes(catalog)
    files = [
        {
            "path": "catalog.json",
            "sha256": hashlib.sha256(catalog_bytes).hexdigest(),
            "size_bytes": len(catalog_bytes),
            "media_type": CATALOG_MEDIA_TYPE,
        }
    ]
    for path in sorted(media):
        content = media[path]
        files.append(
            {
                "path": path,
                "sha256": hashlib.sha256(content).hexdigest(),
                "size_bytes": len(content),
                "media_type": {
                    ".jpg": "image/jpeg",
                    ".png": "image/png",
                    ".webp": "image/webp",
                }[Path(path).suffix],
            }
        )
    manifest = {
        "format": "commerce-architect-catalog",
        "format_version": 1,
        "domain_schema": "product-commerce-catalog/1",
        "entity_versions": {"product": 1, "product_image": 1},
        "required_features": [
            "embedded-images",
            "organization-scope",
            "portable-identities",
            "stock-snapshot",
        ],
        "scope": {"kind": "organization", "coverage": "full"},
        "currency": "USD",
        "inventory_semantics": "snapshot-not-reservation",
        "counts": {
            "products": len(product_records),
            "product_images": len(image_records),
            "media_files": len(media),
        },
        "files": files,
    }
    return encode_package(manifest, catalog, media)


def _publish_without_overwrite(output_path: Path, package: bytes) -> None:
    if not output_path.is_absolute():
        raise CatalogPackageError(
            ErrorCode.OPERATION_NOT_ALLOWED,
            "export output must be an absolute path",
        )
    parent = output_path.parent
    if not parent.is_dir():
        raise CatalogPackageError(
            ErrorCode.OPERATION_NOT_ALLOWED,
            "export output directory must already exist",
        )

    staging_directory = None
    temporary_path = None
    descriptor = None
    try:
        staging_directory = Path(
            tempfile.mkdtemp(prefix=f".{output_path.name}.staging-", dir=parent)
        )
        os.chmod(staging_directory, 0o700)
        temporary_path = staging_directory / output_path.name
        descriptor = os.open(
            temporary_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = None
            handle.write(package)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary_path, output_path)
        temporary_path.unlink()
        temporary_path = None
        directory_descriptor = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except FileExistsError as exc:
        raise CatalogPackageError(
            ErrorCode.OPERATION_NOT_ALLOWED,
            "refusing to overwrite an existing export",
            path=str(output_path),
        ) from exc
    except OSError as exc:
        raise CatalogPackageError(
            ErrorCode.OPERATION_NOT_ALLOWED,
            "could not publish export",
            path=str(output_path),
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass
        if staging_directory is not None:
            try:
                staging_directory.rmdir()
            except OSError:
                pass


def build_export_package(organization_id, *, storage_adapter=None) -> bytes:
    """Return canonical export bytes for one explicitly selected Organization."""

    organization = get_active_organization(organization_id)
    return _build_package(organization.pk, storage_adapter)


def export_catalog(organization_id, output_path, *, storage_adapter=None) -> Path:
    """Build and atomically publish one complete Organization catalog export."""

    organization = get_active_organization(organization_id)
    package = _build_package(organization.pk, storage_adapter)
    output = Path(output_path)
    _publish_without_overwrite(output, package)
    return output
