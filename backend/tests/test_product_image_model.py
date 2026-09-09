import uuid

import pytest
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError

from catalog.admin import ProductImageAdmin
from catalog.models import Product, ProductImage
from organizations.models import Organization


def make_product(name="Product", organization=None):
    organization = organization or Organization.objects.create(name=f"{name} Organization")
    return Product.objects.create(
        name=name,
        description="",
        product_type="physical",
        price="10.00",
        organization=organization,
        sku=f"{name.upper()}-SKU",
        stock_quantity=0,
    )


@pytest.mark.django_db
def test_product_allows_zero_images_and_zero_primary_images():
    product = make_product()
    assert product.images.count() == 0


@pytest.mark.django_db
def test_primary_image_switch_clears_the_previous_primary():
    product = make_product()
    first = ProductImage.objects.create(
        product=product,
        storage_key="catalog/first.jpg",
        is_primary=True,
    )
    second = ProductImage.objects.create(
        product=product,
        storage_key="catalog/second.jpg",
    )
    second.is_primary = True
    second.save()
    first.refresh_from_db()
    assert first.is_primary is False
    assert ProductImage.objects.filter(product=product, is_primary=True).get() == second


@pytest.mark.django_db
def test_database_rejects_two_primary_images():
    product = make_product()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ProductImage.objects.bulk_create(
                [
                    ProductImage(product=product, storage_key="one.jpg", is_primary=True),
                    ProductImage(product=product, storage_key="two.jpg", is_primary=True),
                ]
            )


@pytest.mark.django_db
def test_equal_sort_order_is_tied_by_portable_id():
    product = make_product()
    lower = uuid.UUID("11111111-1111-4111-8111-111111111111")
    higher = uuid.UUID("22222222-2222-4222-8222-222222222222")
    ProductImage.objects.create(
        product=product,
        portable_id=higher,
        storage_key="higher.jpg",
        sort_order=4,
    )
    ProductImage.objects.create(
        product=product,
        portable_id=lower,
        storage_key="lower.jpg",
        sort_order=4,
    )
    assert list(product.images.values_list("portable_id", flat=True)) == [lower, higher]


@pytest.mark.django_db
def test_image_identity_is_unique_per_product_but_scoped_ids_can_repeat():
    first_product = make_product("First")
    second_product = make_product("Second")
    image_id = uuid.uuid4()
    ProductImage.objects.create(
        product=first_product,
        portable_id=image_id,
        storage_key="first.jpg",
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ProductImage.objects.bulk_create(
                [
                    ProductImage(
                        product=first_product,
                        portable_id=image_id,
                        storage_key="duplicate.jpg",
                    )
                ]
            )
    ProductImage.objects.create(
        product=second_product,
        portable_id=image_id,
        storage_key="second.jpg",
    )


@pytest.mark.django_db
def test_image_rejects_negative_sort_and_reparenting():
    product = make_product("Original")
    other_product = make_product("Other")
    image = ProductImage.objects.create(
        product=product,
        storage_key="original.jpg",
    )
    with pytest.raises(ValidationError):
        ProductImage(
            product=product,
            storage_key="negative.jpg",
            sort_order=-1,
        ).full_clean()
    image.product = other_product
    with pytest.raises(ValidationError, match="reparented"):
        image.save()
    image.refresh_from_db()
    assert image.product_id == product.pk


@pytest.mark.django_db
def test_product_deletion_is_protected_when_images_exist():
    product = make_product()
    ProductImage.objects.create(product=product, storage_key="protected.jpg")
    with pytest.raises(ProtectedError):
        product.delete()


@pytest.mark.django_db
def test_product_image_uuid_is_persistent_and_admin_is_superuser_only(rf):
    product = make_product()
    image = ProductImage.objects.create(product=product, storage_key="stable.jpg")
    image_id = image.portable_id
    image.refresh_from_db()
    assert image.portable_id == image_id

    image_admin = ProductImageAdmin(ProductImage, admin.site)
    request = rf.get("/admin/catalog/productimage/")
    request.user = type("User", (), {"is_authenticated": True, "is_active": True, "is_superuser": False})()
    assert image_admin.has_module_permission(request) is False
    request.user.is_superuser = True
    assert image_admin.has_module_permission(request) is True
