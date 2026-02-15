import pytest

from catalog.models import Product


@pytest.mark.django_db
def test_product_list_api_returns_active_product(client):
    Product.objects.create(
        name="API Product",
        description="API product description",
        product_type="physical",
        price="29.99",
        is_active=True,
    )

    response = client.get("/api/products/")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["name"] == "API Product"
