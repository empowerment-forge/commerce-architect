import pytest
from django.contrib.auth.models import User

from catalog.models import Product


@pytest.mark.django_db
def test_registration_success(client):
    response = client.post(
        "/api/auth/register/",
        {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "SecurePass123!",
        },
        content_type="application/json",
    )

    assert response.status_code == 201
    user = User.objects.get(username="newuser")
    assert user.email == "newuser@example.com"
    assert user.check_password("SecurePass123!")


@pytest.mark.django_db
def test_registration_failure_duplicate_user(client):
    User.objects.create_user(username="newuser", password="SecurePass123!")

    response = client.post(
        "/api/auth/register/",
        {
            "username": "newuser",
            "email": "duplicate@example.com",
            "password": "SecurePass123!",
        },
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "username" in response.json()


@pytest.mark.django_db
def test_token_obtain_success(client):
    User.objects.create_user(username="loginuser", password="SecurePass123!")

    response = client.post(
        "/api/auth/token/",
        {"username": "loginuser", "password": "SecurePass123!"},
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.json()
    assert "access" in data
    assert "refresh" in data


@pytest.mark.django_db
def test_token_obtain_failure(client):
    User.objects.create_user(username="loginuser", password="SecurePass123!")

    response = client.post(
        "/api/auth/token/",
        {"username": "loginuser", "password": "WrongPass123!"},
        content_type="application/json",
    )

    assert response.status_code == 401


@pytest.mark.django_db
def test_products_endpoint_requires_jwt(client):
    Product.objects.create(
        name="Protected Product",
        description="Protected product",
        product_type="physical",
        price="99.99",
        is_active=True,
    )

    response = client.get("/api/products/")

    assert response.status_code == 401
