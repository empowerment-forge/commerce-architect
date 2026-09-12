import uuid

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from catalog.models import CatalogOperationReceipt, Product
from catalog.portability.planner import plan_catalog_import
from catalog.portability.importer import apply_catalog_import
from catalog.portability.reset import apply_storefront_reset, preview_storefront_reset
from media_storage.local import LocalMediaStorageAdapter
from organizations.models import Organization


@pytest.fixture(autouse=True)
def restore_catalog_schema():
    executor = MigrationExecutor(connection)
    executor.migrate([
        ("organizations", "0001_initial"),
        ("catalog", "0005_catalog_operation_receipt"),
    ])


def empty_package():
    from tests.test_catalog_import_application import package_for

    return package_for([])


@pytest.mark.django_db(transaction=True)
def test_reset_and_import_append_receipts_without_rewriting_durable_history(tmp_path):
    organization = Organization.objects.create(name="History boundary")
    package = empty_package()
    adapter = LocalMediaStorageAdapter(tmp_path / "media")
    plan = plan_catalog_import(package, organization.pk, mode="merge")
    import_receipt = apply_catalog_import(
        package,
        organization.pk,
        mode="merge",
        operation_id=uuid.uuid4(),
        expected_package_sha256=plan.package_sha256,
        expected_catalog_digest=plan.target_digest,
        storage_adapter=adapter,
    )
    preview = preview_storefront_reset(organization.pk, storage_adapter=adapter)
    reset_receipt = apply_storefront_reset(
        organization.pk,
        operation_id=uuid.uuid4(),
        expected_catalog_digest=preview.target_digest,
        confirmed_organization_id=organization.pk,
        storage_adapter=adapter,
    )

    receipts = list(
        CatalogOperationReceipt.objects.filter(organization=organization)
        .order_by("completed_at")
        .values_list("pk", "operation_type", "pre_catalog_digest", "post_catalog_digest")
    )
    assert [row[0] for row in receipts] == [import_receipt.pk, reset_receipt.pk]
    assert [row[1] for row in receipts] == ["catalog-import", "catalog-reset-storefront"]
    assert all(row[2] and row[3] for row in receipts)


@pytest.mark.django_db(transaction=True)
def test_portability_history_boundary_has_no_order_domain_to_mutate():
    organization = Organization.objects.create(name="No orders")
    assert not hasattr(organization, "orders")
    assert Product.objects.filter(organization=organization).count() == 0
