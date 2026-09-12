import pytest
from django.test import override_settings

from catalog.models import Product, ProductImage
from organizations.models import Organization


def make_product(organization, name, sku, *, is_active=True):
    return Product.objects.create(
        name=name,
        description="",
        product_type="physical",
        price="10.00",
        is_active=is_active,
        organization=organization,
        sku=sku,
        stock_quantity=0,
    )


@pytest.mark.django_db
def test_product_list_api_orders_primary_then_domain_order_and_exposes_public_urls(client):
    organization = Organization.objects.create(name="Image API Organization")
    product = make_product(organization, "Image API Product", "IMAGE-001")
    ProductImage.objects.create(
        product=product,
        storage_key="sha256/" + "a" * 64,
        alt_text="Fallback",
        sort_order=0,
        portable_id="00000000-0000-4000-8000-000000000002",
    )
    ProductImage.objects.create(
        product=product,
        storage_key="sha256/" + "b" * 64,
        alt_text="Primary",
        sort_order=99,
        is_primary=True,
        portable_id="00000000-0000-4000-8000-000000000001",
    )

    with override_settings(
        STOREFRONT_ORGANIZATION_ID=organization.pk,
        MEDIA_PUBLIC_BASE_URL="https://media.example",
    ):
        response = client.get("/api/products/")

    assert response.status_code == 200
    images = response.json()[0]["images"]
    assert [image["alt_text"] for image in images] == ["Primary", "Fallback"]
    assert images[0]["url"] == "https://media.example/sha256/" + "b" * 64
    assert all("storage_key" not in image for image in images)


@pytest.mark.django_db
def test_product_list_api_excludes_inactive_and_foreign_images(client):
    organization = Organization.objects.create(name="Visible Organization")
    foreign = Organization.objects.create(name="Foreign Organization")
    visible = make_product(organization, "Visible", "VISIBLE-001")
    inactive = make_product(organization, "Inactive", "INACTIVE-001", is_active=False)
    ProductImage.objects.create(product=visible, storage_key="sha256/" + "c" * 64)
    ProductImage.objects.create(product=inactive, storage_key="sha256/" + "d" * 64)
    foreign_product = make_product(foreign, "Foreign", "FOREIGN-001")
    ProductImage.objects.create(product=foreign_product, storage_key="sha256/" + "e" * 64)

    with override_settings(
        STOREFRONT_ORGANIZATION_ID=organization.pk,
        MEDIA_PUBLIC_BASE_URL="https://media.example",
    ):
        response = client.get("/api/products/")

    assert response.status_code == 200
    data = response.json()
    assert [product["name"] for product in data] == ["Visible"]
    assert len(data[0]["images"]) == 1
