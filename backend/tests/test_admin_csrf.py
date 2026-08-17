import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings


PUBLIC_HOST = "commerce.example"
PUBLIC_ORIGIN = f"https://{PUBLIC_HOST}"
LOGIN_PATH = "/admin/login/?next=/admin/"


@pytest.fixture
def csrf_client():
    return Client(enforce_csrf_checks=True, HTTP_HOST=PUBLIC_HOST)


@pytest.fixture
def admin_user(db):
    return get_user_model().objects.create_superuser(
        username="admin-csrf-test",
        email="admin-csrf@example.invalid",
        password="test-only-admin-password",
    )


def login_payload(response, *, password="test-only-admin-password"):
    return {
        "username": "admin-csrf-test",
        "password": password,
        "csrfmiddlewaretoken": response.cookies["csrftoken"].value,
        "next": "/admin/",
    }


@override_settings(
    ALLOWED_HOSTS=[PUBLIC_HOST],
    SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
    CSRF_COOKIE_SECURE=True,
    CSRF_COOKIE_SAMESITE="Lax",
)
@pytest.mark.django_db
def test_admin_login_accepts_same_origin_https_csrf_flow(csrf_client, admin_user):
    admin_response = csrf_client.get(
        "/admin/", HTTP_X_FORWARDED_PROTO="https"
    )
    assert admin_response.status_code == 302
    assert admin_response["Location"] == LOGIN_PATH

    login_response = csrf_client.get(
        LOGIN_PATH, HTTP_X_FORWARDED_PROTO="https"
    )
    assert login_response.status_code == 200
    assert b'name="csrfmiddlewaretoken"' in login_response.content
    assert "csrftoken" in login_response.cookies
    assert login_response.cookies["csrftoken"]["path"] == "/"
    assert login_response.cookies["csrftoken"]["secure"] is True
    assert login_response.cookies["csrftoken"]["samesite"] == "Lax"

    post_response = csrf_client.post(
        LOGIN_PATH,
        login_payload(login_response),
        HTTP_X_FORWARDED_PROTO="https",
        HTTP_ORIGIN=PUBLIC_ORIGIN,
        HTTP_REFERER=f"{PUBLIC_ORIGIN}{LOGIN_PATH}",
    )
    assert post_response.status_code == 302
    assert post_response["Location"] == "/admin/"


@override_settings(
    ALLOWED_HOSTS=[PUBLIC_HOST],
    SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
)
@pytest.mark.django_db
def test_admin_login_rejects_missing_cookie_token_and_untrusted_origin(
    csrf_client, admin_user
):
    missing_cookie = csrf_client.post(
        LOGIN_PATH,
        {
            "username": admin_user.username,
            "password": "test-only-admin-password",
            "csrfmiddlewaretoken": "invalid",
            "next": "/admin/",
        },
        HTTP_X_FORWARDED_PROTO="https",
        HTTP_ORIGIN=PUBLIC_ORIGIN,
        HTTP_REFERER=f"{PUBLIC_ORIGIN}{LOGIN_PATH}",
    )
    assert missing_cookie.status_code == 403

    login_response = csrf_client.get(
        LOGIN_PATH, HTTP_X_FORWARDED_PROTO="https"
    )
    missing_token = csrf_client.post(
        LOGIN_PATH,
        {
            "username": admin_user.username,
            "password": "test-only-admin-password",
            "next": "/admin/",
        },
        HTTP_X_FORWARDED_PROTO="https",
        HTTP_ORIGIN=PUBLIC_ORIGIN,
        HTTP_REFERER=f"{PUBLIC_ORIGIN}{LOGIN_PATH}",
    )
    assert missing_token.status_code == 403

    invalid_token = csrf_client.post(
        LOGIN_PATH,
        {
            "username": admin_user.username,
            "password": "test-only-admin-password",
            "csrfmiddlewaretoken": "invalid",
            "next": "/admin/",
        },
        HTTP_X_FORWARDED_PROTO="https",
        HTTP_ORIGIN=PUBLIC_ORIGIN,
        HTTP_REFERER=f"{PUBLIC_ORIGIN}{LOGIN_PATH}",
    )
    assert invalid_token.status_code == 403

    untrusted_origin = csrf_client.post(
        LOGIN_PATH,
        login_payload(login_response),
        HTTP_X_FORWARDED_PROTO="https",
        HTTP_ORIGIN="https://attacker.example",
        HTTP_REFERER="https://attacker.example/admin/login/",
    )
    assert untrusted_origin.status_code == 403


@override_settings(
    ALLOWED_HOSTS=[PUBLIC_HOST],
    SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
)
def test_forwarded_https_controls_django_secure_request_detection():
    secure_response = Client(HTTP_HOST=PUBLIC_HOST).get(
        "/", HTTP_X_FORWARDED_PROTO="https"
    )
    assert secure_response.wsgi_request.is_secure() is True

    insecure_response = Client(HTTP_HOST=PUBLIC_HOST).get(
        "/", HTTP_X_FORWARDED_PROTO="http"
    )
    assert insecure_response.wsgi_request.is_secure() is False
