import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client
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
def test_token_obtain_success_sets_refresh_cookie(client):
    User.objects.create_user(username="loginuser", password="SecurePass123!")

    response = client.post(
        "/api/auth/token/",
        {"username": "loginuser", "password": "SecurePass123!"},
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.json()
    assert "access" in data
    assert "refresh" not in data

    assert "refresh_token" in response.cookies
    refresh_cookie = response.cookies["refresh_token"]
    assert refresh_cookie.value
    assert refresh_cookie["httponly"]
    assert bool(refresh_cookie["secure"]) is settings.REFRESH_COOKIE_SECURE
    assert refresh_cookie["samesite"] == settings.REFRESH_COOKIE_SAMESITE
    assert refresh_cookie["path"] == settings.REFRESH_COOKIE_PATH
    assert refresh_cookie["max-age"] == 7 * 24 * 60 * 60


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
def test_products_endpoint_is_public_without_jwt(client):
    Product.objects.create(
        name="Public Product",
        description="Visible without auth",
        product_type="physical",
        price="99.99",
        is_active=True,
    )

    response = client.get("/api/products/")

    assert response.status_code == 200


@pytest.mark.django_db
def test_refresh_works_using_cookie_and_rotates_token(client):
    User.objects.create_user(username="rotateuser", password="SecurePass123!")

    token_response = client.post(
        "/api/auth/token/",
        {"username": "rotateuser", "password": "SecurePass123!"},
        content_type="application/json",
    )
    original_refresh = token_response.cookies["refresh_token"].value

    refresh_response = client.post("/api/auth/refresh/")

    assert refresh_response.status_code == 200
    assert "access" in refresh_response.json()
    assert "refresh" not in refresh_response.json()
    assert "refresh_token" in refresh_response.cookies
    rotated_refresh = refresh_response.cookies["refresh_token"].value
    assert rotated_refresh != original_refresh


@pytest.mark.django_db
def test_old_refresh_cookie_token_is_blacklisted_after_rotation(client):
    User.objects.create_user(username="oldrefreshuser", password="SecurePass123!")

    token_response = client.post(
        "/api/auth/token/",
        {"username": "oldrefreshuser", "password": "SecurePass123!"},
        content_type="application/json",
    )
    original_refresh = token_response.cookies["refresh_token"].value

    first_refresh_response = client.post("/api/auth/refresh/")
    assert first_refresh_response.status_code == 200

    stale_client = Client()
    stale_client.cookies["refresh_token"] = original_refresh
    second_refresh_response = stale_client.post("/api/auth/refresh/")

    assert second_refresh_response.status_code == 401


@pytest.mark.django_db
def test_blacklisted_refresh_token_rejected(client):
    user = User.objects.create_user(
        username="blacklistuser",
        password="SecurePass123!",
    )
    refresh = RefreshToken.for_user(user)
    refresh.blacklist()

    client.cookies["refresh_token"] = str(refresh)
    response = client.post("/api/auth/refresh/")

    assert response.status_code == 401


@pytest.mark.django_db
def test_refresh_missing_cookie_returns_401(client):
    response = client.post("/api/auth/refresh/")

    assert response.status_code == 401


@pytest.mark.django_db
def test_invalid_refresh_cookie_returns_401(client):
    client.cookies["refresh_token"] = "not-a-valid-jwt"

    response = client.post("/api/auth/refresh/")

    assert response.status_code == 401


@pytest.mark.django_db
def test_access_token_works_for_protected_endpoint(client):
    User.objects.create_user(username="accessuser", password="SecurePass123!")

    token_response = client.post(
        "/api/auth/token/",
        {"username": "accessuser", "password": "SecurePass123!"},
        content_type="application/json",
    )
    access_token = token_response.json()["access"]

    protected_response = client.get(
        "/api/auth/me/",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
    )

    assert protected_response.status_code == 200
    assert protected_response.json()["username"] == "accessuser"


@pytest.mark.django_db
def test_me_endpoint_rejects_unauthenticated_request(client):
    response = client.get("/api/auth/me/")

    assert response.status_code == 401


@pytest.mark.django_db
def test_logout_blacklists_refresh_token_and_clears_cookie(client):
    User.objects.create_user(username="logoutuser", password="SecurePass123!")

    token_response = client.post(
        "/api/auth/token/",
        {"username": "logoutuser", "password": "SecurePass123!"},
        content_type="application/json",
    )
    refresh_token = token_response.cookies["refresh_token"].value

    logout_response = client.post("/api/auth/logout/")

    assert logout_response.status_code == 200
    assert logout_response.json() == {"detail": "Logged out."}
    cleared_cookie = logout_response.cookies["refresh_token"]
    assert cleared_cookie.value == ""
    assert cleared_cookie["max-age"] == 0
    assert cleared_cookie["path"] == "/api/auth/"

    stale_client = Client()
    stale_client.cookies["refresh_token"] = refresh_token
    refresh_response = stale_client.post("/api/auth/refresh/")

    assert refresh_response.status_code == 401
