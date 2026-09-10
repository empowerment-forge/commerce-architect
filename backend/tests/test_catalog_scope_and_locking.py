import threading
import time

import pytest
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.test import override_settings

from catalog.admin import ProductAdmin
from catalog.models import Product, ProductImage
from catalog.services import (
    CatalogBusyError,
    CatalogNotConfigured,
    CatalogScopeError,
    catalog_write_lock,
    scoped_product_images,
    scoped_products,
)
from organizations.models import Organization


def make_product(organization, name, *, product_type="physical", active=True):
    return Product.objects.create(
        name=name,
        description=name,
        product_type=product_type,
        price="10.00",
        is_active=active,
        organization=organization,
        sku=f"{name.upper()}-SKU",
        stock_quantity=0,
    )


@pytest.mark.django_db
def test_product_api_is_explicitly_scoped_to_active_physical_products(client):
    first = Organization.objects.create(name="First")
    second = Organization.objects.create(name="Second")
    make_product(first, "FIRST")
    make_product(first, "FIRST-INACTIVE", active=False)
    make_product(first, "FIRST-SERVICE", product_type="service")
    make_product(second, "SECOND")

    with override_settings(STOREFRONT_ORGANIZATION_ID=first.pk):
        response = client.get("/api/products/")
    assert response.status_code == 200
    assert [item["name"] for item in response.json()] == ["FIRST"]


@pytest.mark.django_db
def test_product_api_fails_closed_without_valid_storefront_configuration(client):
    organization = Organization.objects.create(name="Unselected")
    make_product(organization, "Hidden")
    with override_settings(STOREFRONT_ORGANIZATION_ID=None):
        response = client.get("/api/products/")
    assert response.status_code == 503
    with override_settings(STOREFRONT_ORGANIZATION_ID=999999):
        response = client.get("/api/products/")
    assert response.status_code == 503


@pytest.mark.django_db
def test_scoped_product_and_image_queries_cannot_cross_organizations():
    first = Organization.objects.create(name="First")
    second = Organization.objects.create(name="Second")
    first_product = make_product(first, "FIRST")
    second_product = make_product(second, "SECOND")
    first_image = ProductImage.objects.create(product=first_product, storage_key="first.jpg")
    ProductImage.objects.create(product=second_product, storage_key="second.jpg")

    assert list(scoped_products(first.pk).values_list("pk", flat=True)) == [first_product.pk]
    assert list(scoped_product_images(first.pk).values_list("pk", flat=True)) == [first_image.pk]
    with pytest.raises(CatalogScopeError):
        scoped_products(None)
    with pytest.raises(CatalogScopeError):
        scoped_product_images(0)


@pytest.mark.django_db
def test_admin_queryset_is_scoped_and_product_hard_delete_is_disabled(rf):
    first = Organization.objects.create(name="First")
    second = Organization.objects.create(name="Second")
    first_product = make_product(first, "FIRST")
    second_product = make_product(second, "SECOND")
    product_admin = ProductAdmin(Product, admin.site)
    request = rf.get("/admin/catalog/product/")
    with override_settings(STOREFRONT_ORGANIZATION_ID=first.pk):
        assert list(product_admin.get_queryset(request)) == [first_product]
        assert product_admin.has_delete_permission(request) is False
        second_product.organization = second
        with pytest.raises(ValidationError):
            product_admin.save_model(request, second_product, None, True)


@pytest.mark.django_db(transaction=True)
def test_competing_organization_writers_return_catalog_busy():
    organization = Organization.objects.create(name="Locked")
    started = threading.Event()
    outcome = []

    def competing_writer():
        from django.db import connections

        try:
            connections.close_all()
            started.set()
            with catalog_write_lock(organization.pk):
                outcome.append("acquired")
        except CatalogBusyError as exc:
            outcome.append(exc.code)
        finally:
            connections.close_all()

    with catalog_write_lock(organization.pk):
        worker = threading.Thread(target=competing_writer)
        worker.start()
        assert started.wait(timeout=1)
        worker.join(timeout=7)
        assert worker.is_alive() is False
    assert outcome == ["CATALOG_BUSY"]


@pytest.mark.django_db(transaction=True)
def test_unrelated_organizations_do_not_block_each_other():
    first = Organization.objects.create(name="First")
    second = Organization.objects.create(name="Second")
    outcome = []

    def unrelated_writer():
        from django.db import connections

        try:
            connections.close_all()
            with catalog_write_lock(second.pk):
                outcome.append("acquired")
        finally:
            connections.close_all()

    with catalog_write_lock(first.pk):
        worker = threading.Thread(target=unrelated_writer)
        worker.start()
        worker.join(timeout=2)
        assert worker.is_alive() is False
    assert outcome == ["acquired"]


@pytest.mark.django_db(transaction=True)
def test_organization_lock_serializes_a_supported_writer():
    organization = Organization.objects.create(name="Serialized")
    product = make_product(organization, "SERIALIZED")
    started = threading.Event()
    outcome = []

    def competing_writer():
        from django.db import connections

        try:
            connections.close_all()
            started.set()
            with catalog_write_lock(organization.pk):
                Product.objects.filter(pk=product.pk).update(description="after lock")
                outcome.append("updated")
        finally:
            connections.close_all()

    with catalog_write_lock(organization.pk):
        worker = threading.Thread(target=competing_writer)
        worker.start()
        assert started.wait(timeout=1)
        time.sleep(0.1)
        assert outcome == []
    worker.join(timeout=2)
    assert outcome == ["updated"]
    product.refresh_from_db()
    assert product.description == "after lock"
