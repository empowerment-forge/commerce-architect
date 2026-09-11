import hashlib
import io
import uuid

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from PIL import Image

from catalog.models import CatalogOperationReceipt, Product
from catalog.portability.codec import canonical_json_bytes, encode_package
from catalog.portability.errors import CatalogPackageError
from catalog.portability.importer import apply_catalog_import
from catalog.portability.planner import plan_catalog_import
from catalog.portability.schema import ErrorCode
from media_storage.local import LocalMediaStorageAdapter
from organizations.models import Organization


@pytest.fixture(autouse=True)
def restore_catalog_schema():
    """Migration tests earlier in the repository suite use historical schemas."""
    executor = MigrationExecutor(connection)
    executor.migrate([
        ("organizations", "0001_initial"),
        ("catalog", "0005_catalog_operation_receipt"),
    ])


def manifest_for(catalog, media=()):
    catalog_bytes = canonical_json_bytes(catalog)
    return {
        "format": "commerce-architect-catalog",
        "format_version": 1,
        "domain_schema": "product-commerce-catalog/1",
        "entity_versions": {"product": 1, "product_image": 1},
        "required_features": ["embedded-images", "organization-scope", "portable-identities", "stock-snapshot"],
        "scope": {"kind": "organization", "coverage": "full"},
        "currency": "USD",
        "inventory_semantics": "snapshot-not-reservation",
        "counts": {"products": len(catalog["products"]), "product_images": len(catalog["product_images"]), "media_files": len(media)},
        "files": [{
            "path": "catalog.json",
            "sha256": hashlib.sha256(catalog_bytes).hexdigest(),
            "size_bytes": len(catalog_bytes),
            "media_type": "application/json",
        }] + [{
            "path": path,
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
            "media_type": media_type,
        } for path, content, media_type in media],
    }


def package_for(products, images=(), media=()):
    catalog = {"products": products, "product_images": list(images)}
    return encode_package(manifest_for(catalog, media), catalog, {path: content for path, content, _ in media})


def product(portable_id, sku, *, name=None, status="active", stock=7):
    return {
        "portable_id": portable_id,
        "sku": sku,
        "name": name or sku,
        "description": "description",
        "price": "10.00",
        "stock_quantity": stock,
        "status": status,
    }


def png_bytes(color=(10, 20, 30)):
    output = io.BytesIO()
    Image.new("RGB", (2, 2), color).save(output, format="PNG")
    return output.getvalue()


def apply(package, organization, plan, *, operation_id=None, mode="merge", adapter=None, **kwargs):
    return apply_catalog_import(
        package,
        organization.pk,
        mode=mode,
        operation_id=operation_id or uuid.uuid4(),
        expected_package_sha256=plan.package_sha256,
        expected_catalog_digest=plan.target_digest,
        storage_adapter=adapter,
        **kwargs,
    )


@pytest.mark.django_db(transaction=True)
def test_apply_creates_receipt_and_preserves_stock_on_exact_retry(tmp_path):
    organization = Organization.objects.create(name="Importer")
    package = package_for([product("00000000-0000-4000-8000-000000000001", "NEW", stock=22)])
    plan = plan_catalog_import(package, organization.pk, mode="merge")
    operation_id = uuid.uuid4()
    receipt = apply_catalog_import(
        package,
        organization.pk,
        mode="merge",
        operation_id=operation_id,
        expected_package_sha256=plan.package_sha256,
        expected_catalog_digest=plan.target_digest,
        storage_adapter=LocalMediaStorageAdapter(tmp_path / "media"),
    )

    created = Product.objects.get(organization=organization)
    assert created.stock_quantity == 0
    assert receipt.operation_id == operation_id
    assert CatalogOperationReceipt.objects.count() == 1
    retried = apply_catalog_import(
        package,
        organization.pk,
        mode="merge",
        operation_id=operation_id,
        expected_package_sha256=plan.package_sha256,
        expected_catalog_digest=plan.target_digest,
        storage_adapter=LocalMediaStorageAdapter(tmp_path / "other"),
    )
    assert retried.pk == receipt.pk
    assert Product.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_changed_bytes_are_rejected_before_catalog_work():
    organization = Organization.objects.create(name="Changed")
    package = package_for([])
    with pytest.raises(CatalogPackageError) as exc:
        apply_catalog_import(
            package + b"x",
            organization.pk,
            mode="merge",
            operation_id=uuid.uuid4(),
            expected_package_sha256=hashlib.sha256(package).hexdigest(),
            expected_catalog_digest=plan_catalog_import(package, organization.pk, mode="merge").target_digest,
        )
    assert exc.value.code == ErrorCode.PACKAGE_CHANGED
    assert Product.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_product_failure_rolls_back_catalog_and_receipt(monkeypatch, tmp_path):
    organization = Organization.objects.create(name="Rollback")
    package = package_for([product("00000000-0000-4000-8000-000000000002", "ROLLBACK")])
    plan = plan_catalog_import(package, organization.pk, mode="merge")

    from catalog.portability import importer
    original = importer._apply_products

    def fail_after_apply(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("injected product failure")

    monkeypatch.setattr(importer, "_apply_products", fail_after_apply)
    with pytest.raises(CatalogPackageError) as exc:
        apply_catalog_import(
            package,
            organization.pk,
            mode="merge",
            operation_id=uuid.uuid4(),
            expected_package_sha256=plan.package_sha256,
            expected_catalog_digest=plan.target_digest,
            storage_adapter=LocalMediaStorageAdapter(tmp_path / "media"),
        )
    assert exc.value.code == ErrorCode.IMPORT_FAILED
    assert Product.objects.count() == 0
    assert CatalogOperationReceipt.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_update_noop_replace_and_exact_digest_behavior(tmp_path):
    organization = Organization.objects.create(name="Modes")
    identity = "00000000-0000-4000-8000-000000000003"
    package = package_for([product(identity, "NEW", name="Renamed", status="inactive", stock=99)])
    adapter = LocalMediaStorageAdapter(tmp_path / "media")
    plan = plan_catalog_import(package, organization.pk, mode="merge")
    first = apply(package, organization, plan, adapter=adapter)
    created = Product.objects.get(organization=organization)
    created_at, updated_at = created.created_at, created.updated_at
    assert created.name == "Renamed" and created.is_active is False and created.stock_quantity == 0
    second_plan = plan_catalog_import(package, organization.pk, mode="merge", storage_adapter=adapter)
    second = apply(package, organization, second_plan, adapter=adapter)
    created.refresh_from_db()
    assert second.post_catalog_digest == first.post_catalog_digest
    assert created.created_at == created_at and created.updated_at == updated_at
    assert CatalogOperationReceipt.objects.count() == 2


@pytest.mark.django_db(transaction=True)
def test_authoritative_images_are_created_and_empty_package_removes_them(tmp_path):
    organization = Organization.objects.create(name="Images")
    identity = "00000000-0000-4000-8000-000000000004"
    content = png_bytes()
    digest = hashlib.sha256(content).hexdigest()
    path = f"media/{digest}.png"
    image_id = "00000000-0000-4000-8000-000000000005"
    image = {"portable_id": image_id, "product_portable_id": identity, "asset_path": path, "alt_text": "cover", "sort_order": 0, "is_primary": True}
    adapter = LocalMediaStorageAdapter(tmp_path / "media")
    package = package_for([product(identity, "IMAGE")], [image], [(path, content, "image/png")])
    plan = plan_catalog_import(package, organization.pk, mode="merge", storage_adapter=adapter)
    apply(package, organization, plan, adapter=adapter)
    from catalog.models import ProductImage
    stored = ProductImage.objects.get()
    assert stored.is_primary is True and stored.storage_key == f"sha256/{digest}"
    empty = package_for([product(identity, "IMAGE")])
    empty_plan = plan_catalog_import(empty, organization.pk, mode="merge", storage_adapter=adapter)
    apply(empty, organization, empty_plan, adapter=adapter)
    assert ProductImage.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_preconditions_confirmation_and_media_failure_are_safe(tmp_path):
    organization = Organization.objects.create(name="Guards")
    package = package_for([product("00000000-0000-4000-8000-000000000006", "GUARD")])
    plan = plan_catalog_import(package, organization.pk, mode="merge")
    with pytest.raises(CatalogPackageError) as changed:
        apply_catalog_import(package + b"x", organization.pk, mode="merge", operation_id=uuid.uuid4(), expected_package_sha256=plan.package_sha256, expected_catalog_digest=plan.target_digest)
    assert changed.value.code == ErrorCode.PACKAGE_CHANGED
    with pytest.raises(CatalogPackageError) as confirmed:
        apply_catalog_import(package, organization.pk, mode="replace-storefront", operation_id=uuid.uuid4(), expected_package_sha256=plan.package_sha256, expected_catalog_digest=plan.target_digest)
    assert confirmed.value.code == ErrorCode.OPERATION_NOT_ALLOWED
    assert Product.objects.count() == 0
