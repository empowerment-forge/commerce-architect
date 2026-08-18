import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from accounts.models import AccountProfile, AccountSecurityState, EmailVerification


PASSWORD = "SecurePass123!"
NEW_PASSWORD = "OtherSecure456!"


def registration_payload(**overrides):
    payload = {
        "username": "identityuser",
        "first_name": "Identity",
        "last_name": "User",
        "email": "Identity.User@Example.COM",
        "password": PASSWORD,
    }
    payload.update(overrides)
    return payload


def verified_user(
    username="identityuser",
    email="identity.user@example.com",
    password=PASSWORD,
    first_name="Identity",
    last_name="User",
):
    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
    )
    EmailVerification.objects.create(
        user=user,
        normalized_email=email.casefold(),
        verified_at=timezone.now(),
    )
    return user


def login(client, identifier="identityuser", password=PASSWORD):
    return client.post(
        "/api/auth/token/",
        {"username": identifier, "password": password},
        content_type="application/json",
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "overrides,field",
    [
        ({"first_name": ""}, "first_name"),
        ({"first_name": "   "}, "first_name"),
        ({"last_name": ""}, "last_name"),
        ({"last_name": "   "}, "last_name"),
    ],
)
def test_registration_requires_nonblank_names(client, overrides, field):
    response = client.post(
        "/api/auth/register/",
        registration_payload(**overrides),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert field in response.json()
    assert not User.objects.filter(username="identityuser").exists()


@pytest.mark.django_db
def test_registration_persists_names_and_optional_phone(client):
    without_phone = client.post(
        "/api/auth/register/",
        registration_payload(),
        content_type="application/json",
    )
    assert without_phone.status_code == 201
    user = User.objects.get(username="identityuser")
    assert (user.first_name, user.last_name) == ("Identity", "User")
    assert not AccountProfile.objects.filter(user=user).exists()
    assert without_phone.json()["phone"] == ""

    with_phone = client.post(
        "/api/auth/register/",
        registration_payload(
            username="phoneuser",
            email="phone@example.com",
            phone=" +1 (317) 555-0123 ",
        ),
        content_type="application/json",
    )
    assert with_phone.status_code == 201
    assert AccountProfile.objects.get(user__username="phoneuser").phone == (
        "+1 (317) 555-0123"
    )


@pytest.mark.django_db
@pytest.mark.parametrize("phone", ["call-me", "+12", "+1 317 555 0123 ext 9"])
def test_registration_rejects_malformed_nonblank_phone(client, phone):
    response = client.post(
        "/api/auth/register/",
        registration_payload(phone=phone),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert "phone" in response.json()
    assert not User.objects.filter(username="identityuser").exists()


@pytest.mark.django_db
def test_login_accepts_username_and_normalized_email(client, settings):
    settings.AUTH_REQUIRE_VERIFIED_EMAIL = True
    verified_user(email="Identity.User@Example.COM")

    assert login(client).status_code == 200
    assert login(client, "  IDENTITY.USER@example.com ").status_code == 200


@pytest.mark.django_db
def test_login_failures_are_generic_and_verification_rules_apply(client, settings):
    settings.AUTH_REQUIRE_VERIFIED_EMAIL = True
    user = verified_user()
    wrong = login(client, user.email, "wrong-password")
    unknown = login(client, "unknown@example.com", "wrong-password")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"]

    user.email_verification.verified_at = None
    user.email_verification.save(update_fields=["verified_at"])
    blocked = login(client, user.email)
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "email_not_verified"


@pytest.mark.django_db
def test_login_rejects_username_email_identity_ambiguity(client):
    verified_user(username="email-owner", email="shared@example.com")
    username_owner = verified_user(
        username="shared@example.com", email="other@example.com"
    )

    ambiguous = login(client, "shared@example.com")
    assert ambiguous.status_code == 401
    assert "given credentials" in ambiguous.json()["detail"]
    assert login(client, username_owner.username, "wrong-password").status_code == 401


@pytest.mark.django_db
def test_me_returns_complete_identity_and_empty_phone_consistently(client):
    user = verified_user(first_name="Legacy", last_name="")
    access = login(client).json()["access"]
    response = client.get(
        "/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {access}"
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": user.id,
        "username": "identityuser",
        "first_name": "Legacy",
        "last_name": "",
        "phone": "",
        "email": "identity.user@example.com",
        "email_verified": True,
        "email_verified_at": response.json()["email_verified_at"],
    }


@pytest.mark.django_db
def test_profile_update_is_authorized_scoped_and_preserves_blank_phone(client):
    user = verified_user()
    profile = AccountProfile.objects.create(user=user, phone="+1 317 555 0100")
    security = AccountSecurityState.objects.create(user=user, session_generation=4)
    original_password = user.password
    unauthenticated = client.patch(
        "/api/auth/me/",
        {"first_name": "No", "last_name": "Access", "phone": ""},
        content_type="application/json",
    )
    assert unauthenticated.status_code == 401

    access = login(client).json()["access"]
    response = client.patch(
        "/api/auth/me/",
        {
            "first_name": " Updated ",
            "last_name": " Person ",
            "phone": "",
            "username": "attacker-change",
            "email": "attacker@example.com",
            "password": "plaintext",
            "session_generation": 99,
        },
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {access}",
    )

    assert response.status_code == 200
    user.refresh_from_db()
    profile.refresh_from_db()
    security.refresh_from_db()
    assert (user.first_name, user.last_name) == ("Updated", "Person")
    assert profile.phone == "+1 317 555 0100"
    assert user.username == "identityuser"
    assert user.email == "identity.user@example.com"
    assert user.password == original_password
    assert security.session_generation == 4


@pytest.mark.django_db
def test_profile_update_valid_phone_and_invalid_update_is_atomic(client):
    user = verified_user()
    access = login(client).json()["access"]
    updated = client.patch(
        "/api/auth/me/",
        {"first_name": "First", "last_name": "Last", "phone": "+44 20 7946 0958"},
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {access}",
    )
    assert updated.status_code == 200
    assert updated.json()["phone"] == "+44 20 7946 0958"

    invalid = client.patch(
        "/api/auth/me/",
        {"first_name": "Partial", "last_name": "", "phone": "invalid"},
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {access}",
    )
    assert invalid.status_code == 400
    user.refresh_from_db()
    assert (user.first_name, user.last_name) == ("First", "Last")
    assert user.account_profile.phone == "+44 20 7946 0958"


@pytest.mark.django_db
def test_password_change_validates_without_revoking_on_failure(client):
    user = verified_user()
    logged_in = login(client)
    access = logged_in.json()["access"]
    original_refresh = logged_in.cookies["refresh_token"].value
    generation = AccountSecurityState.objects.get(user=user).session_generation

    for payload in (
        {"new_password": NEW_PASSWORD, "new_password_confirmation": NEW_PASSWORD},
        {
            "current_password": "wrong-password",
            "new_password": NEW_PASSWORD,
            "new_password_confirmation": NEW_PASSWORD,
        },
        {
            "current_password": PASSWORD,
            "new_password": NEW_PASSWORD,
            "new_password_confirmation": "different",
        },
        {
            "current_password": PASSWORD,
            "new_password": "password",
            "new_password_confirmation": "password",
        },
    ):
        response = client.post(
            "/api/auth/password-change/",
            payload,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {access}",
        )
        assert response.status_code == 400
        assert PASSWORD not in str(response.json())
        assert NEW_PASSWORD not in str(response.json())

    user.refresh_from_db()
    assert user.check_password(PASSWORD)
    assert AccountSecurityState.objects.get(user=user).session_generation == generation
    refresh_client = client.__class__()
    refresh_client.cookies["refresh_token"] = original_refresh
    assert refresh_client.post("/api/auth/refresh/").status_code == 200


@pytest.mark.django_db
def test_password_change_revokes_all_refresh_sessions_and_requires_new_login(client):
    user = verified_user()
    first_login = login(client)
    old_refresh = first_login.cookies["refresh_token"].value
    second_client = client.__class__()
    second_login = login(second_client)
    other_refresh = second_login.cookies["refresh_token"].value
    access = first_login.json()["access"]

    changed = client.post(
        "/api/auth/password-change/",
        {
            "current_password": PASSWORD,
            "new_password": NEW_PASSWORD,
            "new_password_confirmation": NEW_PASSWORD,
        },
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {access}",
    )
    assert changed.status_code == 200
    assert changed.json()["code"] == "password_changed"
    assert changed.cookies["refresh_token"]["max-age"] == 0
    user.refresh_from_db()
    assert user.check_password(NEW_PASSWORD)
    assert AccountSecurityState.objects.get(user=user).session_generation == 1

    for refresh in (old_refresh, other_refresh):
        stale = client.__class__()
        stale.cookies["refresh_token"] = refresh
        assert stale.post("/api/auth/refresh/").status_code == 401
    assert login(client, password=PASSWORD).status_code == 401
    assert login(client, password=NEW_PASSWORD).status_code == 200
