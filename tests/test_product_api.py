import pytest
from django.contrib.auth.models import User

from catalog.models import Product


@pytest.mark.django_db
def test_product_list_api_returns_active_product(client):
    User.objects.create_user(username="apiuser", password="SecurePass123!")
    Product.objects.create(
        name="API Product",
        description="API product description",
        product_type="physical",
        price="29.99",
        is_active=True,
    )

    token_response = client.post(
        "/api/auth/token/",
        {"username": "apiuser", "password": "SecurePass123!"},
        content_type="application/json",
    )
    access_token = token_response.json()["access"]
    response = client.get(
        "/api/products/",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["name"] == "API Product"
