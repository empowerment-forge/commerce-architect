import pytest
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken

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


@pytest.mark.django_db
def test_refresh_token_rotation_enabled(client):
    User.objects.create_user(username="rotateuser", password="SecurePass123!")

    token_response = client.post(
        "/api/auth/token/",
        {"username": "rotateuser", "password": "SecurePass123!"},
        content_type="application/json",
    )
    original_refresh = token_response.json()["refresh"]

    refresh_response = client.post(
        "/api/auth/token/refresh/",
        {"refresh": original_refresh},
        content_type="application/json",
    )

    assert refresh_response.status_code == 200
    assert "access" in refresh_response.json()
    assert "refresh" in refresh_response.json()
    assert refresh_response.json()["refresh"] != original_refresh


@pytest.mark.django_db
def test_old_refresh_token_invalid_after_rotation(client):
    User.objects.create_user(username="oldrefreshuser", password="SecurePass123!")

    token_response = client.post(
        "/api/auth/token/",
        {"username": "oldrefreshuser", "password": "SecurePass123!"},
        content_type="application/json",
    )
    original_refresh = token_response.json()["refresh"]

    first_refresh_response = client.post(
        "/api/auth/token/refresh/",
        {"refresh": original_refresh},
        content_type="application/json",
    )
    assert first_refresh_response.status_code == 200

    second_refresh_response = client.post(
        "/api/auth/token/refresh/",
        {"refresh": original_refresh},
        content_type="application/json",
    )

    assert second_refresh_response.status_code == 401


@pytest.mark.django_db
def test_blacklisted_refresh_token_rejected(client):
    user = User.objects.create_user(
        username="blacklistuser",
        password="SecurePass123!",
    )
    refresh = RefreshToken.for_user(user)
    refresh.blacklist()

    response = client.post(
        "/api/auth/token/refresh/",
        {"refresh": str(refresh)},
        content_type="application/json",
    )

    assert response.status_code == 401


@pytest.mark.django_db
def test_access_token_works_after_refresh_rotation(client):
    User.objects.create_user(username="accessuser", password="SecurePass123!")
    Product.objects.create(
        name="Token Protected Product",
        description="Only for authenticated users",
        product_type="physical",
        price="49.99",
        is_active=True,
    )

    token_response = client.post(
        "/api/auth/token/",
        {"username": "accessuser", "password": "SecurePass123!"},
        content_type="application/json",
    )
    access_token = token_response.json()["access"]
    original_refresh = token_response.json()["refresh"]

    refresh_response = client.post(
        "/api/auth/token/refresh/",
        {"refresh": original_refresh},
        content_type="application/json",
    )
    assert refresh_response.status_code == 200

    protected_response = client.get(
        "/api/products/",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
    )

    assert protected_response.status_code == 200
