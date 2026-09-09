import uuid
from decimal import Decimal

import pytest
from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.core.exceptions import ValidationError

from catalog.models import Product


@pytest.mark.django_db(transaction=True)
def test_prepare_migration_backfills_identity_without_inventing_catalog_facts():
    executor = MigrationExecutor(connection)
    executor.migrate(
        [("organizations", "0001_initial"), ("catalog", "0001_initial")]
    )
    old_apps = executor.loader.project_state(
        [("catalog", "0001_initial"), ("organizations", "0001_initial")]
    ).apps
    LegacyProduct = old_apps.get_model("catalog", "Product")

    first = LegacyProduct.objects.create(
        name="Legacy One",
        description="First legacy description",
        product_type="physical",
        price="11.10",
        is_active=True,
    )
    second = LegacyProduct.objects.create(
        name="Legacy Two",
        description="Second legacy description",
        product_type="service",
        price="22.20",
        is_active=False,
    )
    original = {
        first.pk: (
            first.name,
            first.description,
            first.product_type,
            Decimal("11.10"),
            first.is_active,
            first.created_at,
        ),
        second.pk: (
            second.name,
            second.description,
            second.product_type,
            Decimal("22.20"),
            second.is_active,
            second.created_at,
        ),
    }

    executor = MigrationExecutor(connection)
    executor.migrate(
        [
            ("organizations", "0001_initial"),
            ("catalog", "0002_prepare_catalog_portability"),
        ]
    )
    executor = MigrationExecutor(connection)
    current_apps = executor.loader.project_state(
        [
            ("organizations", "0001_initial"),
            ("catalog", "0002_prepare_catalog_portability"),
        ]
    ).apps
    CurrentProduct = current_apps.get_model("catalog", "Product")
    migrated = list(CurrentProduct.objects.order_by("pk"))

    assert [product.pk for product in migrated] == [first.pk, second.pk]
    assert len({product.portable_id for product in migrated}) == 2
    assert all(product.portable_id.version == 4 for product in migrated)
    for product in migrated:
        assert (
            product.name,
            product.description,
            product.product_type,
            product.price,
            product.is_active,
        ) == original[product.pk][:-1]
        assert product.created_at == original[product.pk][-1]
        assert product.updated_at == product.created_at
        assert product.organization_id is None
        assert product.sku is None
        assert product.stock_quantity is None
    assert settings.CATALOG_PORTABILITY_ENABLED is False

    stable_before = {
        product.pk: product.portable_id
        for product in CurrentProduct.objects.order_by("pk")
    }
    executor = MigrationExecutor(connection)
    executor.migrate(
        [
            ("organizations", "0001_initial"),
            ("catalog", "0002_prepare_catalog_portability"),
        ]
    )
    stable_after = {
        product.pk: product.portable_id
        for product in CurrentProduct.objects.order_by("pk")
    }
    assert stable_after == stable_before


@pytest.mark.django_db
def test_new_product_receives_persistent_uuid_and_requires_transitional_fields():
    from organizations.models import Organization

    organization = Organization.objects.create(name="Product Organization")
    product = Product(
        name="New Product",
        description="New product",
        product_type="physical",
        price="12.34",
        organization=organization,
        sku="NEW-001",
        stock_quantity=4,
    )
    product.full_clean()
    product.save()
    assert product.portable_id.version == 4
    product_id = product.portable_id
    product.refresh_from_db()
    assert product.portable_id == product_id


@pytest.mark.django_db
def test_malformed_or_non_v4_supplied_uuid_is_rejected():
    from organizations.models import Organization

    organization = Organization.objects.create(name="UUID Organization")
    valid_fields = {
        "name": "UUID Product",
        "description": "",
        "product_type": "physical",
        "price": "1.00",
        "organization": organization,
        "sku": "UUID-001",
        "stock_quantity": 0,
    }
    with pytest.raises(ValidationError):
        Product(**valid_fields, portable_id="not-a-uuid").full_clean()
    with pytest.raises(ValidationError):
        Product(**valid_fields, portable_id=uuid.uuid1()).full_clean()
