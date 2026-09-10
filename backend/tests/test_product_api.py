import pytest
from django.test import override_settings

from catalog.models import Product
from organizations.models import Organization


@pytest.mark.django_db
def test_product_list_api_returns_active_product_without_auth(client):
    organization = Organization.objects.create(name="API Organization")
    Product.objects.create(
        name="API Product",
        description="API product description",
        product_type="physical",
        price="29.99",
        is_active=True,
        organization=organization,
        sku="API-001",
        stock_quantity=0,
    )

    with override_settings(STOREFRONT_ORGANIZATION_ID=organization.pk):
        response = client.get("/api/products/")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["name"] == "API Product"
