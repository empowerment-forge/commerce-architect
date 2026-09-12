from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import AccountSecurityState
from accounts.serializers import SessionTokenObtainPairSerializer
from accounts.services import change_password_and_revoke_sessions
from organizations.authorization import OperatorAuthorizationDenied, resolve_operator_authorization
from organizations.models import Organization, OrganizationMembership
from organizations.permissions import ORGANIZATION_CAPABILITIES_MANAGE
from organizations.reauthentication import (
    RECENT_AUTHENTICATION_PURPOSE,
    verify_recent_authentication,
)

from tests.test_organization_membership import membership, verified_user


def access_token(user, *, session_id="test-session", generation=None):
    security, _ = AccountSecurityState.objects.get_or_create(user=user)
    generation = security.session_generation if generation is None else generation
    refresh = RefreshToken.for_user(user)
    refresh["session_generation"] = generation
    if session_id is not None:
        refresh["session_id"] = session_id
    return str(refresh.access_token)


def request_with_claims(user, session_id="test-session", generation=None):
    security, _ = AccountSecurityState.objects.get_or_create(user=user)
    return SimpleNamespace(
        user=user,
        auth={
            "user_id": user.pk,
            "session_id": session_id,
            "session_generation": security.session_generation if generation is None else generation,
            "token_type": "access",
        },
    )


@pytest.fixture
def owner_context(db):
    organization = Organization.objects.create(name="Reauthentication Organization")
    user = verified_user("reauth-owner")
    membership(organization, user, OrganizationMembership.ROLE_OWNER)
    return organization, user


def authenticated_client(user, *, session_id="test-session", generation=None):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token(user, session_id=session_id, generation=generation)}")
    return client


@pytest.mark.django_db
def test_correct_password_returns_opaque_five_minute_proof(owner_context):
    organization, user = owner_context
    response = authenticated_client(user).post(
        "/api/auth/reauthenticate/",
        {
            "organization_id": organization.pk,
            "purpose": RECENT_AUTHENTICATION_PURPOSE,
            "password": "password-for-tests",
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["expires_in"] == 300
    proof = response.json()["proof"]
    assert isinstance(proof, str)
    assert "reauth-owner" not in proof
    assert verify_recent_authentication(
        request=request_with_claims(user),
        organization_id=organization.pk,
        purpose=RECENT_AUTHENTICATION_PURPOSE,
        proof=proof,
    )


@pytest.mark.django_db
def test_wrong_password_is_rejected_and_failures_are_throttled(owner_context):
    organization, user = owner_context
    cache.clear()
    client = authenticated_client(user)
    payload = {
        "organization_id": organization.pk,
        "purpose": RECENT_AUTHENTICATION_PURPOSE,
        "password": "wrong-password",
    }
    responses = [client.post("/api/auth/reauthenticate/", payload, format="json") for _ in range(6)]
    assert [response.status_code for response in responses[:5]] == [400] * 5
    assert responses[5].status_code == 429


@pytest.mark.django_db
def test_unsupported_purpose_and_ineligible_roles_are_denied(owner_context):
    organization, owner = owner_context
    client = authenticated_client(owner)
    response = client.post(
        "/api/auth/reauthenticate/",
        {"organization_id": organization.pk, "purpose": "other", "password": "password-for-tests"},
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["code"] == "unsupported_purpose"

    manager = verified_user("reauth-manager")
    membership(organization, manager, OrganizationMembership.ROLE_MANAGER)
    response = authenticated_client(manager).post(
        "/api/auth/reauthenticate/",
        {"organization_id": organization.pk, "purpose": RECENT_AUTHENTICATION_PURPOSE, "password": "password-for-tests"},
        format="json",
    )
    assert response.status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("status", [OrganizationMembership.STATUS_SUSPENDED, OrganizationMembership.STATUS_REVOKED])
def test_inactive_membership_is_denied(owner_context, status):
    organization, user = owner_context
    membership_record = OrganizationMembership.objects.get(organization=organization, user=user)
    OrganizationMembership.objects.filter(pk=membership_record.pk).update(status=status)
    response = authenticated_client(user).post(
        "/api/auth/reauthenticate/",
        {"organization_id": organization.pk, "purpose": RECENT_AUTHENTICATION_PURPOSE, "password": "password-for-tests"},
        format="json",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_unverified_user_and_missing_session_id_are_denied(owner_context):
    organization, user = owner_context
    user.email_verification.verified_at = None
    user.email_verification.save(update_fields=["verified_at", "updated_at"])
    response = authenticated_client(user).post(
        "/api/auth/reauthenticate/",
        {"organization_id": organization.pk, "purpose": RECENT_AUTHENTICATION_PURPOSE, "password": "password-for-tests"},
        format="json",
    )
    assert response.status_code == 403

    user.email_verification.verified_at = timezone.now()
    user.email_verification.save(update_fields=["verified_at", "updated_at"])
    response = authenticated_client(user, session_id=None).post(
        "/api/auth/reauthenticate/",
        {"organization_id": organization.pk, "purpose": RECENT_AUTHENTICATION_PURPOSE, "password": "password-for-tests"},
        format="json",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_proof_is_bound_to_session_generation_organization_and_purpose(owner_context):
    organization, user = owner_context
    response = authenticated_client(user).post(
        "/api/auth/reauthenticate/",
        {"organization_id": organization.pk, "purpose": RECENT_AUTHENTICATION_PURPOSE, "password": "password-for-tests"},
        format="json",
    )
    proof = response.json()["proof"]
    other_organization = Organization.objects.create(name="Other Reauthentication Organization")
    request = request_with_claims(user)
    assert not verify_recent_authentication(request=request, organization_id=other_organization.pk, purpose=RECENT_AUTHENTICATION_PURPOSE, proof=proof)
    assert not verify_recent_authentication(request=request, organization_id=organization.pk, purpose="other", proof=proof)
    assert not verify_recent_authentication(request=request_with_claims(user, session_id="other-session"), organization_id=organization.pk, purpose=RECENT_AUTHENTICATION_PURPOSE, proof=proof)
    assert not verify_recent_authentication(request=request_with_claims(user, generation=1), organization_id=organization.pk, purpose=RECENT_AUTHENTICATION_PURPOSE, proof=proof)


@pytest.mark.django_db
def test_proof_expiry_tampering_and_password_change_invalidation(owner_context):
    organization, user = owner_context
    request = request_with_claims(user)
    response = authenticated_client(user).post(
        "/api/auth/reauthenticate/",
        {"organization_id": organization.pk, "purpose": RECENT_AUTHENTICATION_PURPOSE, "password": "password-for-tests"},
        format="json",
    )
    proof = response.json()["proof"]
    assert not verify_recent_authentication(request=request, organization_id=organization.pk, purpose=RECENT_AUTHENTICATION_PURPOSE, proof=proof + "tampered")
    with patch("django.core.signing.time.time", return_value=timezone.now().timestamp() + 301):
        assert not verify_recent_authentication(request=request, organization_id=organization.pk, purpose=RECENT_AUTHENTICATION_PURPOSE, proof=proof)

    change_password_and_revoke_sessions(user.pk, "password-for-tests", "new-password-for-tests")
    assert not verify_recent_authentication(request=request, organization_id=organization.pk, purpose=RECENT_AUTHENTICATION_PURPOSE, proof=proof)


@pytest.mark.django_db
def test_refresh_preserves_session_id_and_proof_does_not_elevate_permissions(owner_context):
    organization, owner = owner_context
    issued = SessionTokenObtainPairSerializer(
        data={"username": owner.username, "password": "password-for-tests"}
    )
    assert issued.is_valid(), issued.errors
    issued_refresh = RefreshToken(issued.validated_data["refresh"])
    assert isinstance(issued_refresh.get("session_id"), str)
    assert issued_refresh.access_token["session_id"] == issued_refresh["session_id"]

    refresh = RefreshToken.for_user(owner)
    refresh["session_generation"] = 0
    refresh["session_id"] = "stable-session"
    assert refresh.access_token["session_id"] == "stable-session"

    manager = verified_user("reauth-manager-no-elevation")
    membership(organization, manager, OrganizationMembership.ROLE_MANAGER)
    with pytest.raises(OperatorAuthorizationDenied):
        resolve_operator_authorization(
            request_with_claims(manager),
            organization.pk,
            ORGANIZATION_CAPABILITIES_MANAGE,
        )
