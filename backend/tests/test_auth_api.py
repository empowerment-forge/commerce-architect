import pytest
from django.core import mail
from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from accounts.models import EmailVerification
from accounts.services import issue_verification, token_digest
from catalog.models import Product


def registration_payload(**overrides):
    payload = {
        "username": "newuser",
        "email": "NewUser@Example.COM",
        "password": "SecurePass123!",
    }
    payload.update(overrides)
    return payload


def verification_params(message=None):
    message = message or mail.outbox[-1]
    link = next(line for line in message.body.splitlines() if line.startswith("http"))
    parsed = urlparse(link)
    query = parse_qs(parsed.query)
    return parsed, {"uid": query["uid"][0], "token": query["token"][0]}


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
    assert response.json()["email_verified"] is False
    assert "access" not in response.json()
    verification = user.email_verification
    assert verification.normalized_email == "newuser@example.com"
    assert verification.token_digest
    assert len(verification.token_digest) == 64
    assert len(mail.outbox) == 1
    parsed, params = verification_params()
    assert parsed.scheme == "http"
    assert parsed.netloc == "localhost:5173"
    assert parsed.path == "/verify-email"
    assert params["token"] not in verification.token_digest
    assert token_digest(params["token"]) == verification.token_digest


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
def test_registration_rejects_duplicate_email_case_insensitively(client):
    first = client.post(
        "/api/auth/register/",
        registration_payload(),
        content_type="application/json",
    )
    assert first.status_code == 201

    duplicate = client.post(
        "/api/auth/register/",
        registration_payload(username="other", email=" newuser@example.com "),
        content_type="application/json",
    )

    assert duplicate.status_code == 400
    assert "email" in duplicate.json()


@pytest.mark.django_db
def test_registration_applies_django_password_validation(client):
    response = client.post(
        "/api/auth/register/",
        registration_payload(password="password"),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "password" in response.json()
    assert not User.objects.filter(username="newuser").exists()


@pytest.mark.django_db
def test_registration_delivery_failure_retains_unverified_account(client):
    with patch("accounts.views.send_verification_email", side_effect=OSError):
        response = client.post(
            "/api/auth/register/",
            registration_payload(),
            content_type="application/json",
        )

    assert response.status_code == 503
    assert response.json()["code"] == "verification_delivery_failed"
    user = User.objects.get(username="newuser")
    assert user.email_verification.verified_at is None


@pytest.mark.django_db
def test_verification_success_and_reuse_is_idempotent(client):
    client.post(
        "/api/auth/register/",
        registration_payload(),
        content_type="application/json",
    )
    _, params = verification_params()

    response = client.post(
        "/api/auth/verify-email/", params, content_type="application/json"
    )
    reused = client.post(
        "/api/auth/verify-email/", params, content_type="application/json"
    )

    assert response.status_code == 200
    assert response.json()["code"] == "verified"
    assert response.json()["email"] == "newuser@example.com"
    assert response.json()["verified_at"]
    assert reused.status_code == 200
    assert reused.json()["code"] == "already_verified"


@pytest.mark.django_db
def test_verification_rejects_tampered_wrong_and_expired_tokens(client, settings):
    client.post(
        "/api/auth/register/",
        registration_payload(),
        content_type="application/json",
    )
    _, params = verification_params()

    tampered = client.post(
        "/api/auth/verify-email/",
        {**params, "token": f"{params['token']}x"},
        content_type="application/json",
    )
    wrong = client.post(
        "/api/auth/verify-email/",
        {**params, "uid": "00000000-0000-0000-0000-000000000000"},
        content_type="application/json",
    )
    settings.AUTH_EMAIL_VERIFICATION_TTL_SECONDS = 1
    verification = EmailVerification.objects.get(user__username="newuser")
    verification.token_created_at = timezone.now() - timedelta(seconds=2)
    verification.save(update_fields=["token_created_at"])
    expired = client.post(
        "/api/auth/verify-email/", params, content_type="application/json"
    )

    assert tampered.status_code == 400
    assert wrong.status_code == 400
    assert expired.status_code == 400
    assert expired.json()["code"] == "invalid_or_expired_token"


@pytest.mark.django_db
def test_resend_is_enumeration_resistant_and_supersedes_token(client):
    client.post(
        "/api/auth/register/",
        registration_payload(),
        content_type="application/json",
    )
    _, original = verification_params()
    verification = EmailVerification.objects.get(user__username="newuser")
    verification.last_sent_at = timezone.now() - timedelta(minutes=2)
    verification.save(update_fields=["last_sent_at"])

    existing = client.post(
        "/api/auth/resend-verification/",
        {"email": "NEWUSER@example.com"},
        content_type="application/json",
    )
    unknown = client.post(
        "/api/auth/resend-verification/",
        {"email": "unknown@example.com"},
        content_type="application/json",
    )
    _, replacement = verification_params()

    assert existing.status_code == unknown.status_code == 202
    assert existing.json() == unknown.json()
    assert len(mail.outbox) == 2
    assert replacement["token"] != original["token"]
    stale = client.post(
        "/api/auth/verify-email/", original, content_type="application/json"
    )
    assert stale.status_code == 400


@pytest.mark.django_db
def test_resend_cooldown_and_verified_account_send_nothing(client):
    client.post(
        "/api/auth/register/",
        registration_payload(),
        content_type="application/json",
    )
    _, params = verification_params()
    cooldown = client.post(
        "/api/auth/resend-verification/",
        {"email": "newuser@example.com"},
        content_type="application/json",
    )
    assert cooldown.status_code == 202
    assert len(mail.outbox) == 1

    client.post("/api/auth/verify-email/", params, content_type="application/json")
    verification = EmailVerification.objects.get(user__username="newuser")
    verification.last_sent_at = timezone.now() - timedelta(minutes=2)
    verification.save(update_fields=["last_sent_at"])
    client.post(
        "/api/auth/resend-verification/",
        {"email": "newuser@example.com"},
        content_type="application/json",
    )
    assert len(mail.outbox) == 1


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
def test_login_enforcement_blocks_unverified_and_allows_verified(client, settings):
    settings.AUTH_REQUIRE_VERIFIED_EMAIL = True
    client.post(
        "/api/auth/register/",
        registration_payload(),
        content_type="application/json",
    )
    _, params = verification_params()

    blocked = client.post(
        "/api/auth/token/",
        {"username": "newuser", "password": "SecurePass123!"},
        content_type="application/json",
    )
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "email_not_verified"
    assert "refresh_token" not in blocked.cookies

    client.post("/api/auth/verify-email/", params, content_type="application/json")
    allowed = client.post(
        "/api/auth/token/",
        {"username": "newuser", "password": "SecurePass123!"},
        content_type="application/json",
    )
    assert allowed.status_code == 200
    assert "refresh_token" in allowed.cookies


@pytest.mark.django_db
def test_login_enforcement_disabled_allows_unverified(client, settings):
    settings.AUTH_REQUIRE_VERIFIED_EMAIL = False
    client.post(
        "/api/auth/register/",
        registration_payload(),
        content_type="application/json",
    )

    response = client.post(
        "/api/auth/token/",
        {"username": "newuser", "password": "SecurePass123!"},
        content_type="application/json",
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_email_change_invalidates_verification_and_old_token(client, settings):
    settings.AUTH_REQUIRE_VERIFIED_EMAIL = True
    client.post(
        "/api/auth/register/",
        registration_payload(),
        content_type="application/json",
    )
    _, old_params = verification_params()
    client.post(
        "/api/auth/verify-email/", old_params, content_type="application/json"
    )
    login = client.post(
        "/api/auth/token/",
        {"username": "newuser", "password": "SecurePass123!"},
        content_type="application/json",
    )
    access = login.json()["access"]

    changed = client.post(
        "/api/auth/change-email/",
        {"email": " NewAddress@Example.COM "},
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {access}",
    )
    _, new_params = verification_params()

    assert changed.status_code == 200
    assert changed.json()["email"] == "newaddress@example.com"
    user = User.objects.get(username="newuser")
    assert user.email == "newaddress@example.com"
    assert user.email_verification.verified_at is None
    assert user.email_verification.normalized_email == "newaddress@example.com"

    stale = client.post(
        "/api/auth/verify-email/", old_params, content_type="application/json"
    )
    assert stale.status_code == 400

    me_unverified = client.get(
        "/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {access}"
    )
    assert me_unverified.json()["email"] == "newaddress@example.com"
    assert me_unverified.json()["email_verified"] is False
    assert me_unverified.json()["email_verified_at"] is None

    blocked_login = Client().post(
        "/api/auth/token/",
        {"username": "newuser", "password": "SecurePass123!"},
        content_type="application/json",
    )
    assert blocked_login.status_code == 403

    verified = client.post(
        "/api/auth/verify-email/", new_params, content_type="application/json"
    )
    assert verified.status_code == 200
    assert verified.json()["email"] == "newaddress@example.com"
    me_verified = client.get(
        "/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {access}"
    )
    assert me_verified.json()["email_verified"] is True


@pytest.mark.django_db
def test_email_change_rejects_duplicate_and_resend_uses_only_current_email(client):
    other = User.objects.create_user(
        username="other",
        email="reserved@example.com",
        password="SecurePass123!",
    )
    EmailVerification.objects.create(
        user=other,
        normalized_email="reserved@example.com",
    )
    client.post(
        "/api/auth/register/",
        registration_payload(),
        content_type="application/json",
    )
    login = client.post(
        "/api/auth/token/",
        {"username": "newuser", "password": "SecurePass123!"},
        content_type="application/json",
    )
    access = login.json()["access"]

    duplicate = client.post(
        "/api/auth/change-email/",
        {"email": "RESERVED@example.com"},
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {access}",
    )
    assert duplicate.status_code == 400

    changed = client.post(
        "/api/auth/change-email/",
        {"email": "current@example.com"},
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {access}",
    )
    assert changed.status_code == 200
    assert mail.outbox[-1].to == ["current@example.com"]
    sent_count = len(mail.outbox)

    old_resend = client.post(
        "/api/auth/resend-verification/",
        {"email": "newuser@example.com"},
        content_type="application/json",
    )
    assert old_resend.status_code == 202
    assert len(mail.outbox) == sent_count


@pytest.mark.django_db
def test_email_change_delivery_failure_keeps_new_address_unverified(client):
    client.post(
        "/api/auth/register/",
        registration_payload(),
        content_type="application/json",
    )
    login = client.post(
        "/api/auth/token/",
        {"username": "newuser", "password": "SecurePass123!"},
        content_type="application/json",
    )
    with patch("accounts.views.send_verification_email", side_effect=OSError):
        response = client.post(
            "/api/auth/change-email/",
            {"email": "delivery-failed@example.com"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {login.json()['access']}",
        )

    assert response.status_code == 503
    user = User.objects.get(username="newuser")
    assert user.email == "delivery-failed@example.com"
    assert user.email_verification.verified_at is None


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
