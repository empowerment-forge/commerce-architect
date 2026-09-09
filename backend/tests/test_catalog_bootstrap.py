import json
from decimal import Decimal
from importlib import import_module
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor

from catalog.bootstrap import (
    BootstrapValidationError,
    apply_mapping,
    mapping_fingerprint,
    validate_mapping,
)
from catalog.models import Product
from organizations.models import Organization


def _target(executor, catalog_migration):
    return [
        ("organizations", "0001_initial"),
        ("catalog", catalog_migration),
    ]


@pytest.mark.django_db(transaction=True)
def test_empty_database_migrates_to_final_foundation_without_seed_data():
    executor = MigrationExecutor(connection)
    executor.migrate(_target(executor, "0003_enforce_catalog_foundation"))
    apps = executor.loader.project_state(
        _target(executor, "0003_enforce_catalog_foundation")
    ).apps
    assert apps.get_model("catalog", "Product").objects.count() == 0
    assert apps.get_model("organizations", "Organization").objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_final_migration_rejects_unresolved_populated_rows():
    executor = MigrationExecutor(connection)
    executor.migrate(_target(executor, "0002_prepare_catalog_portability"))
    apps = executor.loader.project_state(
        _target(executor, "0002_prepare_catalog_portability")
    ).apps
    LegacyProduct = apps.get_model("catalog", "Product")
    LegacyProduct.objects.create(
        name="Unresolved legacy physical",
        description="",
        product_type="physical",
        price=Decimal("10.00"),
        is_active=True,
    )
    try:
        migration = import_module(
            "catalog.migrations.0003_enforce_catalog_foundation"
        )
        with pytest.raises(RuntimeError, match="incomplete Product PKs"):
            migration.assert_catalog_foundation_complete(apps, None)
    finally:
        LegacyProduct.objects.all().delete()
        executor = MigrationExecutor(connection)
        executor.migrate(_target(executor, "0003_enforce_catalog_foundation"))


@pytest.mark.django_db(transaction=True)
def test_reviewed_bootstrap_preserves_identity_and_existing_fields():
    executor = MigrationExecutor(connection)
    executor.migrate(_target(executor, "0002_prepare_catalog_portability"))
    apps = executor.loader.project_state(
        _target(executor, "0002_prepare_catalog_portability")
    ).apps
    LegacyOrganization = apps.get_model("organizations", "Organization")
    LegacyProduct = apps.get_model("catalog", "Product")
    organization = LegacyOrganization.objects.create(name="Reviewed Organization")
    product = LegacyProduct.objects.create(
        name="Legacy physical",
        description="Preserve me",
        product_type="physical",
        price=Decimal("19.99"),
        is_active=False,
    )
    portable_id = product.portable_id
    created_at = product.created_at
    mapping = {
        "organization_id": organization.pk,
        "products": [
            {"product_pk": product.pk, "sku": "LEGACY-1", "stock_quantity": 0}
        ],
    }
    plan = apply_mapping(mapping, organization.pk, mapping_fingerprint(mapping))
    assert plan.assignments == ((product.pk, "LEGACY-1", 0),)
    executor = MigrationExecutor(connection)
    executor.migrate(_target(executor, "0003_enforce_catalog_foundation"))
    apps = executor.loader.project_state(
        _target(executor, "0003_enforce_catalog_foundation")
    ).apps
    migrated = apps.get_model("catalog", "Product").objects.get(pk=product.pk)
    assert migrated.portable_id == portable_id
    assert migrated.created_at == created_at
    assert migrated.name == "Legacy physical"
    assert migrated.description == "Preserve me"
    assert migrated.product_type == "physical"
    assert migrated.price == Decimal("19.99")
    assert migrated.is_active is False
    assert migrated.organization_id == organization.pk
    assert migrated.sku == "LEGACY-1"
    assert migrated.stock_quantity == 0


@pytest.mark.django_db
def test_bootstrap_rejects_missing_unknown_duplicate_and_invalid_rows():
    organization = Organization.objects.create(name="Bootstrap Organization")
    product = Product.objects.create(
        name="Physical",
        description="",
        product_type="physical",
        price="1.00",
        organization=organization,
        sku="OLD-1",
        stock_quantity=0,
    )
    cases = [
        {
            "organization_id": organization.pk,
            "products": [],
        },
        {
            "organization_id": organization.pk,
            "products": [
                {"product_pk": product.pk + 100, "sku": "NEW-1", "stock_quantity": 0}
            ],
        },
        {
            "organization_id": organization.pk,
            "products": [
                {"product_pk": product.pk, "sku": "SAME", "stock_quantity": 0},
                {"product_pk": product.pk, "sku": "SAME-2", "stock_quantity": 0},
            ],
        },
        {
            "organization_id": organization.pk,
            "products": [
                {"product_pk": product.pk, "sku": "bad sku", "stock_quantity": 0}
            ],
        },
        {
            "organization_id": organization.pk,
            "products": [
                {"product_pk": product.pk, "sku": "NEW-1", "stock_quantity": -1}
            ],
        },
    ]
    for mapping in cases:
        with pytest.raises(BootstrapValidationError):
            validate_mapping(mapping, organization.pk)


@pytest.mark.django_db
def test_bootstrap_rejects_service_rows_and_preserves_rows_on_apply_failure(monkeypatch):
    organization = Organization.objects.create(name="Bootstrap Organization")
    first = Product.objects.create(
        name="First",
        description="",
        product_type="physical",
        price="1.00",
        organization=organization,
        sku="FIRST",
        stock_quantity=2,
    )
    second = Product.objects.create(
        name="Second",
        description="",
        product_type="physical",
        price="2.00",
        organization=organization,
        sku="SECOND",
        stock_quantity=3,
    )
    service = Product.objects.create(
        name="Legacy service",
        description="",
        product_type="service",
        price="3.00",
        organization=organization,
        sku="SERVICE",
        stock_quantity=0,
    )
    service_mapping = {
        "organization_id": organization.pk,
        "products": [
            {"product_pk": first.pk, "sku": "FIRST", "stock_quantity": 0},
            {"product_pk": second.pk, "sku": "SECOND", "stock_quantity": 0},
            {"product_pk": service.pk, "sku": "SERVICE-2", "stock_quantity": 0},
        ],
    }
    with pytest.raises(BootstrapValidationError, match="unsupported service"):
        validate_mapping(service_mapping, organization.pk)
    service.delete()

    mapping = {
        "organization_id": organization.pk,
        "products": [
            {"product_pk": first.pk, "sku": "FIRST-NEW", "stock_quantity": 0},
            {"product_pk": second.pk, "sku": "SECOND-NEW", "stock_quantity": 0},
        ],
    }
    original_filter = Product.objects.filter
    calls = {"count": 0}

    def fail_on_second_update(*args, **kwargs):
        if "pk" in kwargs:
            calls["count"] += 1
            if calls["count"] == 2:
                raise RuntimeError("simulated apply failure")
        return original_filter(*args, **kwargs)

    monkeypatch.setattr(Product.objects, "filter", fail_on_second_update)
    with pytest.raises(RuntimeError, match="simulated apply failure"):
        apply_mapping(mapping, organization.pk, mapping_fingerprint(mapping))
    assert Product.objects.get(pk=first.pk).sku == "FIRST"
    assert Product.objects.get(pk=second.pk).sku == "SECOND"


@pytest.mark.django_db
def test_final_constraints_reject_duplicate_sku_and_portable_identity():
    first_org = Organization.objects.create(name="First")
    second_org = Organization.objects.create(name="Second")
    first = Product.objects.create(
        name="First",
        description="",
        product_type="physical",
        price="1.00",
        organization=first_org,
        sku="SHARED",
        stock_quantity=0,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Product.objects.bulk_create([
                Product(
                    name="Duplicate SKU",
                    description="",
                    product_type="physical",
                    price="2.00",
                    organization=first_org,
                    sku="SHARED",
                    stock_quantity=0,
                )
            ])
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Product.objects.bulk_create([
                Product(
                    name="Duplicate identity",
                    description="",
                    product_type="physical",
                    price="2.00",
                    organization=first_org,
                    sku="OTHER",
                    stock_quantity=0,
                    portable_id=first.portable_id,
                )
            ])
    Product.objects.create(
        name="Other scope",
        description="",
        product_type="physical",
        price="2.00",
        organization=second_org,
        sku="SHARED",
        stock_quantity=0,
        portable_id=first.portable_id,
    )


@pytest.mark.django_db
def test_catalog_bootstrap_command_validate_and_apply(tmp_path, capsys):
    organization = Organization.objects.create(name="Command Organization")
    product = Product.objects.create(
        name="Command Product",
        description="",
        product_type="physical",
        price="4.00",
        organization=organization,
        sku="COMMAND-OLD",
        stock_quantity=5,
    )
    mapping = {
        "organization_id": organization.pk,
        "products": [
            {"product_pk": product.pk, "sku": "COMMAND-NEW", "stock_quantity": 0}
        ],
    }
    path = tmp_path / "mapping.json"
    path.write_text(json.dumps(mapping), encoding="utf-8")
    call_command(
        "catalog_bootstrap",
        mapping=str(path),
        organization=organization.pk,
        validate_only=True,
    )
    output = capsys.readouterr().out
    fingerprint = mapping_fingerprint(mapping)
    assert fingerprint in output
    assert Product.objects.get(pk=product.pk).sku == "COMMAND-OLD"
    with pytest.raises(CommandError, match="fingerprint"):
        call_command(
            "catalog_bootstrap",
            mapping=str(path),
            organization=organization.pk,
            fingerprint="0" * 64,
        )
    call_command(
        "catalog_bootstrap",
        mapping=str(path),
        organization=organization.pk,
        fingerprint=fingerprint,
    )
    product.refresh_from_db()
    assert product.sku == "COMMAND-NEW"
    assert product.stock_quantity == 0
