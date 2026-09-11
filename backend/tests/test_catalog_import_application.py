import hashlib
import uuid

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

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


def manifest_for(catalog):
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
        "counts": {"products": len(catalog["products"]), "product_images": 0, "media_files": 0},
        "files": [{
            "path": "catalog.json",
            "sha256": hashlib.sha256(catalog_bytes).hexdigest(),
            "size_bytes": len(catalog_bytes),
            "media_type": "application/json",
        }],
    }


def package_for(products):
    catalog = {"products": products, "product_images": []}
    return encode_package(manifest_for(catalog), catalog, {})


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
