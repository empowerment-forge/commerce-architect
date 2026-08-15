import pytest
from django.core import mail
from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, override_settings
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from accounts.models import AccountSecurityState, EmailVerification, PasswordRecoveryState
from accounts.services import (
    issue_verification,
    send_verification_email,
    token_digest,
    verification_url,
)
from django.core.cache import cache
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
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


def verified_recovery_user(username="recoveryuser", email="recovery@example.com"):
    user = User.objects.create_user(
        username=username,
        email=email,
        password="SecurePass123!",
    )
    EmailVerification.objects.create(
        user=user,
        normalized_email=email,
        verified_at=timezone.now(),
    )
    return user


def recovery_params(message=None):
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
def test_readable_console_url_round_trips_through_verification_api(
    client, settings, capsys
):
    settings.MAILERS = {
        "default": {"BACKEND": "accounts.mail.ReadableConsoleEmailBackend"}
    }
    user = User.objects.create_user(
        username="consoleuser",
        email="consoleuser@example.com",
        password="SecurePass123!",
    )
    verification = EmailVerification.objects.create(
        user=user,
        normalized_email=user.email,
    )
    issued = issue_verification(verification)
    expected_url = verification_url(issued)

    send_verification_email(issued)
    output = capsys.readouterr().out
    printed_url = next(line for line in output.splitlines() if line.startswith("http"))
    parsed = urlparse(printed_url)
    query = parse_qs(parsed.query)
    params = {"uid": query["uid"][0], "token": query["token"][0]}

    verification.refresh_from_db()
    assert printed_url == expected_url
    assert "=3D" not in printed_url
    assert params["uid"] == str(verification.pk)
    assert token_digest(params["token"]) == verification.token_digest

    response = client.post(
        "/api/auth/verify-email/", params, content_type="application/json"
    )
    assert response.status_code == 200
    assert response.json()["code"] == "verified"


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
@pytest.mark.parametrize(
    "password, expected_message",
    [
        ("Ab1!", "at least 8 characters"),
        ("password", "too common"),
        ("123456789", "entirely numeric"),
    ],
)
def test_registration_applies_each_configured_password_validator(
    client, password, expected_message
):
    response = client.post(
        "/api/auth/register/",
        registration_payload(password=password),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "password" in response.json()
    assert any(expected_message in message for message in response.json()["password"])
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

    unknown = client.post(
        "/api/auth/resend-verification/",
        {"email": "unknown@example.com"},
        content_type="application/json",
    )
    assert unknown.status_code == 202
    assert cooldown.json() == unknown.json()

    client.post("/api/auth/verify-email/", params, content_type="application/json")
    verification = EmailVerification.objects.get(user__username="newuser")
    verification.last_sent_at = timezone.now() - timedelta(minutes=2)
    verification.save(update_fields=["last_sent_at"])
    verified = client.post(
        "/api/auth/resend-verification/",
        {"email": "newuser@example.com"},
        content_type="application/json",
    )
    assert len(mail.outbox) == 1
    assert verified.status_code == 202
    assert verified.json() == cooldown.json()


@pytest.mark.django_db
def test_public_resend_rejects_malformed_email_without_account_detail(client):
    response = client.post(
        "/api/auth/resend-verification/",
        {"email": "not-an-email"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json() == {"email": ["Enter a valid email address."]}


@pytest.mark.django_db
def test_authenticated_resend_targets_current_email_and_rotates_token(client):
    client.post(
        "/api/auth/register/",
        registration_payload(),
        content_type="application/json",
    )
    _, original = verification_params()
    verification = EmailVerification.objects.get(user__username="newuser")
    verification.last_sent_at = timezone.now() - timedelta(minutes=2)
    verification.save(update_fields=["last_sent_at"])
    login = client.post(
        "/api/auth/token/",
        {"username": "newuser", "password": "SecurePass123!"},
        content_type="application/json",
    )

    resent = client.post(
        "/api/auth/resend-verification-authenticated/",
        {"email": "attacker-controlled@example.com"},
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {login.json()['access']}",
    )
    _, replacement = verification_params()

    assert resent.status_code == 202
    assert resent.json()["code"] == "verification_email_sent"
    assert mail.outbox[-1].to == ["newuser@example.com"]
    assert replacement["token"] != original["token"]
    assert client.post(
        "/api/auth/verify-email/", original, content_type="application/json"
    ).status_code == 400
    assert client.post(
        "/api/auth/verify-email/", replacement, content_type="application/json"
    ).status_code == 200


@pytest.mark.django_db
def test_authenticated_resend_reports_cooldown_without_sending(client):
    client.post(
        "/api/auth/register/",
        registration_payload(),
        content_type="application/json",
    )
    _, params = verification_params()
    client.post("/api/auth/verify-email/", params, content_type="application/json")
    login = client.post(
        "/api/auth/token/",
        {"username": "newuser", "password": "SecurePass123!"},
        content_type="application/json",
    )
    changed = client.post(
        "/api/auth/change-email/",
        {"email": "changed@example.com"},
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {login.json()['access']}",
    )
    assert changed.status_code == 200
    verification = EmailVerification.objects.get(user__username="newuser")
    original_digest = verification.token_digest

    response = client.post(
        "/api/auth/resend-verification-authenticated/",
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {login.json()['access']}",
    )

    verification.refresh_from_db()
    assert response.status_code == 429
    assert response.json()["code"] == "resend_cooldown"
    assert response.json()["retry_after_seconds"] > 0
    assert verification.token_digest == original_digest
    assert len(mail.outbox) == 2


@pytest.mark.django_db
def test_authenticated_resend_does_not_send_for_verified_account(client):
    client.post(
        "/api/auth/register/",
        registration_payload(),
        content_type="application/json",
    )
    _, params = verification_params()
    client.post("/api/auth/verify-email/", params, content_type="application/json")
    login = client.post(
        "/api/auth/token/",
        {"username": "newuser", "password": "SecurePass123!"},
        content_type="application/json",
    )
    verification = EmailVerification.objects.get(user__username="newuser")
    verification.last_sent_at = timezone.now() - timedelta(minutes=2)
    verification.save(update_fields=["last_sent_at"])

    response = client.post(
        "/api/auth/resend-verification-authenticated/",
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {login.json()['access']}",
    )

    assert response.status_code == 409
    assert response.json()["code"] == "email_already_verified"
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_authenticated_resend_requires_authentication(client):
    response = client.post(
        "/api/auth/resend-verification-authenticated/",
        content_type="application/json",
    )

    assert response.status_code == 401


@pytest.mark.django_db
def test_authenticated_resend_reports_delivery_failure(client):
    client.post(
        "/api/auth/register/",
        registration_payload(),
        content_type="application/json",
    )
    verification = EmailVerification.objects.get(user__username="newuser")
    verification.last_sent_at = timezone.now() - timedelta(minutes=2)
    verification.save(update_fields=["last_sent_at"])
    login = client.post(
        "/api/auth/token/",
        {"username": "newuser", "password": "SecurePass123!"},
        content_type="application/json",
    )

    with patch("accounts.views.send_verification_email", side_effect=OSError):
        response = client.post(
            "/api/auth/resend-verification-authenticated/",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {login.json()['access']}",
        )

    assert response.status_code == 503
    assert response.json()["code"] == "verification_delivery_failed"


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
def test_malformed_access_token_is_rejected_without_credential_detail(client):
    response = client.get(
        "/api/auth/me/",
        HTTP_AUTHORIZATION="Bearer not-a-valid-jwt",
    )

    assert response.status_code == 401
    assert response.json()["code"] == "token_not_valid"
    assert "not-a-valid-jwt" not in response.content.decode()


@pytest.mark.django_db
def test_expired_access_is_rejected_while_refresh_cookie_issues_replacement(client):
    user = User.objects.create_user(username="lifecycleuser", password="SecurePass123!")
    login_response = client.post(
        "/api/auth/token/",
        {"username": "lifecycleuser", "password": "SecurePass123!"},
        content_type="application/json",
    )
    refresh_cookie = login_response.cookies["refresh_token"]
    refresh = RefreshToken(refresh_cookie.value)
    expired_access = AccessToken.for_user(user)
    expired_access.set_exp(from_time=timezone.now() - timedelta(minutes=11))

    protected_response = client.get(
        "/api/auth/me/",
        HTTP_AUTHORIZATION=f"Bearer {expired_access}",
    )
    refresh_response = client.post("/api/auth/refresh/")

    assert settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"] == timedelta(minutes=10)
    assert settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"] == timedelta(days=7)
    assert expired_access["exp"] < int(timezone.now().timestamp())
    assert refresh["exp"] > int(timezone.now().timestamp())
    assert refresh_cookie["httponly"] is True
    assert refresh_cookie["max-age"] == 7 * 24 * 60 * 60
    assert protected_response.status_code == 401
    assert protected_response.json()["code"] == "token_not_valid"
    assert refresh_response.status_code == 200
    replacement = AccessToken(refresh_response.json()["access"])
    assert replacement["exp"] > int(timezone.now().timestamp())
    assert "refresh_token" in refresh_response.cookies


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


@pytest.mark.django_db
def test_password_recovery_request_eligible_sends_digest_only_email(client):
    user = verified_recovery_user()

    response = client.post(
        "/api/auth/password-reset/request/",
        {"email": " Recovery@Example.COM "},
        content_type="application/json",
    )

    assert response.status_code == 202
    assert response.json() == {
        "detail": "If an eligible account exists, password recovery instructions will be sent."
    }
    recovery = PasswordRecoveryState.objects.get(user=user)
    assert len(recovery.token_digest) == 64
    assert recovery.token_created_at
    assert recovery.last_sent_at
    assert len(mail.outbox) == 1
    parsed, params = recovery_params()
    assert parsed.path == "/reset-password"
    assert params["token"] not in recovery.token_digest
    assert mail.outbox[0].to == ["recovery@example.com"]


@pytest.mark.django_db
@pytest.mark.parametrize("account_state", ["unknown", "inactive", "unverified"])
def test_password_recovery_request_is_enumeration_resistant(client, account_state):
    if account_state == "inactive":
        user = verified_recovery_user()
        user.is_active = False
        user.save(update_fields=["is_active"])
    elif account_state == "unverified":
        user = User.objects.create_user(
            username="unverifiedrecovery",
            email="recovery@example.com",
            password="SecurePass123!",
        )
        EmailVerification.objects.create(
            user=user,
            normalized_email=user.email,
        )

    response = client.post(
        "/api/auth/password-reset/request/",
        {"email": "recovery@example.com"},
        content_type="application/json",
    )

    assert response.status_code == 202
    assert response.json()["detail"].startswith("If an eligible account exists")
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_password_recovery_request_validates_email_and_throttles(client):
    cache.clear()
    malformed = client.post(
        "/api/auth/password-reset/request/",
        {"email": "not-an-email"},
        content_type="application/json",
    )
    assert malformed.status_code == 400
    assert "email" in malformed.json()

    responses = [
        client.post(
            "/api/auth/password-reset/request/",
            {"email": f"unknown{index}@example.com"},
            content_type="application/json",
        )
        for index in range(5)
    ]
    assert [item.status_code for item in responses[:4]] == [202] * 4
    assert responses[4].status_code == 429


@pytest.mark.django_db
@override_settings(
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": (
            "rest_framework_simplejwt.authentication.JWTAuthentication",
        ),
        "DEFAULT_THROTTLE_RATES": {"password_recovery_request": "5/minute"},
        "NUM_PROXIES": 1,
    }
)
def test_password_recovery_throttle_ignores_spoofed_forwarding_hops(client):
    cache.clear()
    responses = [
        client.post(
            "/api/auth/password-reset/request/",
            {"email": f"unknown{index}@example.com"},
            content_type="application/json",
            HTTP_X_FORWARDED_FOR=f"198.51.100.{index}, 203.0.113.10",
        )
        for index in range(6)
    ]

    assert [item.status_code for item in responses[:5]] == [202] * 5
    assert responses[5].status_code == 429


@pytest.mark.django_db
def test_password_recovery_cooldown_and_reissue_supersedes_old_token(client, settings):
    verified_recovery_user()
    settings.AUTH_PASSWORD_RECOVERY_RESEND_COOLDOWN_SECONDS = 60
    first = client.post(
        "/api/auth/password-reset/request/",
        {"email": "recovery@example.com"},
        content_type="application/json",
    )
    _, first_params = recovery_params()
    second = client.post(
        "/api/auth/password-reset/request/",
        {"email": "recovery@example.com"},
        content_type="application/json",
    )
    assert first.status_code == second.status_code == 202
    assert len(mail.outbox) == 1

    recovery = PasswordRecoveryState.objects.get()
    recovery.last_sent_at = timezone.now() - timedelta(seconds=61)
    recovery.save(update_fields=["last_sent_at"])
    client.post(
        "/api/auth/password-reset/request/",
        {"email": "recovery@example.com"},
        content_type="application/json",
    )
    _, replacement_params = recovery_params()
    assert len(mail.outbox) == 2

    old = client.post(
        "/api/auth/password-reset/confirm/",
        {**first_params, "new_password": "OtherSecure456!", "confirm_password": "OtherSecure456!"},
        content_type="application/json",
    )
    replacement = client.post(
        "/api/auth/password-reset/confirm/",
        {**replacement_params, "new_password": "OtherSecure456!", "confirm_password": "OtherSecure456!"},
        content_type="application/json",
    )
    assert old.status_code == 400
    assert replacement.status_code == 200


@pytest.mark.django_db
def test_password_recovery_delivery_failure_releases_cooldown_without_leak(
    client, caplog
):
    verified_recovery_user()
    provider_secret = "provider-secret-must-not-leak"
    with patch(
        "accounts.views.send_password_recovery_email",
        side_effect=RuntimeError(provider_secret),
    ):
        response = client.post(
            "/api/auth/password-reset/request/",
            {"email": "recovery@example.com"},
            content_type="application/json",
        )
    recovery = PasswordRecoveryState.objects.get()
    assert response.status_code == 202
    assert recovery.token_digest == ""
    assert recovery.token_created_at is None
    assert recovery.last_sent_at is None
    assert provider_secret not in caplog.text
    assert "Password recovery email delivery failed." in caplog.text

    retry = client.post(
        "/api/auth/password-reset/request/",
        {"email": "recovery@example.com"},
        content_type="application/json",
    )
    assert retry.status_code == 202
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_password_recovery_rejects_expired_tampered_and_reused_tokens(client, settings):
    verified_recovery_user()
    client.post(
        "/api/auth/password-reset/request/",
        {"email": "recovery@example.com"},
        content_type="application/json",
    )
    _, params = recovery_params()
    tampered = client.post(
        "/api/auth/password-reset/confirm/",
        {**params, "token": params["token"] + "x", "new_password": "OtherSecure456!", "confirm_password": "OtherSecure456!"},
        content_type="application/json",
    )
    assert tampered.status_code == 400

    settings.AUTH_PASSWORD_RECOVERY_TTL_SECONDS = 1
    recovery = PasswordRecoveryState.objects.get()
    recovery.token_created_at = timezone.now() - timedelta(seconds=2)
    recovery.save(update_fields=["token_created_at"])
    expired = client.post(
        "/api/auth/password-reset/confirm/",
        {**params, "new_password": "OtherSecure456!", "confirm_password": "OtherSecure456!"},
        content_type="application/json",
    )
    assert expired.status_code == 400

    settings.AUTH_PASSWORD_RECOVERY_TTL_SECONDS = 1800
    recovery.token_created_at = timezone.now()
    recovery.save(update_fields=["token_created_at"])
    success = client.post(
        "/api/auth/password-reset/confirm/",
        {**params, "new_password": "OtherSecure456!", "confirm_password": "OtherSecure456!"},
        content_type="application/json",
    )
    reused = client.post(
        "/api/auth/password-reset/confirm/",
        {**params, "new_password": "ThirdSecure789!", "confirm_password": "ThirdSecure789!"},
        content_type="application/json",
    )
    assert success.status_code == 200
    assert reused.status_code == 400
    assert reused.json()["code"] == "invalid_or_expired_token"


@pytest.mark.django_db
def test_password_recovery_password_feedback_does_not_consume_token(client):
    verified_recovery_user()
    client.post(
        "/api/auth/password-reset/request/",
        {"email": "recovery@example.com"},
        content_type="application/json",
    )
    _, params = recovery_params()
    mismatch = client.post(
        "/api/auth/password-reset/confirm/",
        {**params, "new_password": "OtherSecure456!", "confirm_password": "different"},
        content_type="application/json",
    )
    weak = client.post(
        "/api/auth/password-reset/confirm/",
        {**params, "new_password": "password", "confirm_password": "password"},
        content_type="application/json",
    )
    recovery = PasswordRecoveryState.objects.get()
    assert mismatch.status_code == 400
    assert "confirm_password" in mismatch.json()
    assert weak.status_code == 400
    assert "new_password" in weak.json()
    assert recovery.token_digest


@pytest.mark.django_db
def test_password_recovery_invalidated_by_email_or_password_change(client):
    user = verified_recovery_user()
    client.post(
        "/api/auth/password-reset/request/",
        {"email": user.email},
        content_type="application/json",
    )
    _, email_params = recovery_params()
    from accounts.services import change_email

    change_email(user, "changed@example.com")
    email_invalid = client.post(
        "/api/auth/password-reset/confirm/",
        {**email_params, "new_password": "OtherSecure456!", "confirm_password": "OtherSecure456!"},
        content_type="application/json",
    )
    assert email_invalid.status_code == 400

    user.email = "recovery@example.com"
    user.save(update_fields=["email"])
    verification = user.email_verification
    verification.normalized_email = user.email
    verification.verified_at = timezone.now()
    verification.save(update_fields=["normalized_email", "verified_at"])
    client.post(
        "/api/auth/password-reset/request/",
        {"email": user.email},
        content_type="application/json",
    )
    _, password_params = recovery_params()
    user.set_password("ExternallyChanged456!")
    user.save(update_fields=["password"])
    password_invalid = client.post(
        "/api/auth/password-reset/confirm/",
        {**password_params, "new_password": "OtherSecure456!", "confirm_password": "OtherSecure456!"},
        content_type="application/json",
    )
    assert password_invalid.status_code == 400


@pytest.mark.django_db
def test_session_generation_claim_legacy_refresh_and_rotation(client):
    user = verified_recovery_user()
    login = client.post(
        "/api/auth/token/",
        {"username": user.username, "password": "SecurePass123!"},
        content_type="application/json",
    )
    refresh = RefreshToken(login.cookies["refresh_token"].value)
    assert refresh["session_generation"] == 0
    assert AccountSecurityState.objects.get(user=user).session_generation == 0
    rotated = client.post("/api/auth/refresh/")
    assert rotated.status_code == 200
    assert RefreshToken(rotated.cookies["refresh_token"].value)["session_generation"] == 0

    legacy_client = Client()
    legacy_client.cookies["refresh_token"] = str(RefreshToken.for_user(user))
    assert legacy_client.post("/api/auth/refresh/").status_code == 200


@pytest.mark.django_db
def test_successful_reset_revokes_refresh_sessions_and_requires_login(client):
    user = verified_recovery_user()
    login = client.post(
        "/api/auth/token/",
        {"username": user.username, "password": "SecurePass123!"},
        content_type="application/json",
    )
    old_refresh = login.cookies["refresh_token"].value
    client.post(
        "/api/auth/password-reset/request/",
        {"email": user.email},
        content_type="application/json",
    )
    _, params = recovery_params()
    reset = client.post(
        "/api/auth/password-reset/confirm/",
        {**params, "new_password": "OtherSecure456!", "confirm_password": "OtherSecure456!"},
        content_type="application/json",
    )

    assert reset.status_code == 200
    assert reset.json() == {"code": "password_reset", "detail": "Password changed. Please log in."}
    assert reset.cookies["refresh_token"]["max-age"] == 0
    user.refresh_from_db()
    assert user.check_password("OtherSecure456!")
    assert AccountSecurityState.objects.get(user=user).session_generation == 1
    assert BlacklistedToken.objects.filter(token__user=user).count() == OutstandingToken.objects.filter(user=user).count()

    stale = Client()
    stale.cookies["refresh_token"] = old_refresh
    assert stale.post("/api/auth/refresh/").status_code == 401
    legacy_after_reset = RefreshToken.for_user(user)
    stale.cookies["refresh_token"] = str(legacy_after_reset)
    assert stale.post("/api/auth/refresh/").status_code == 401
    assert client.post(
        "/api/auth/token/",
        {"username": user.username, "password": "SecurePass123!"},
        content_type="application/json",
    ).status_code == 401
    assert client.post(
        "/api/auth/token/",
        {"username": user.username, "password": "OtherSecure456!"},
        content_type="application/json",
    ).status_code == 200
