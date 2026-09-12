from types import SimpleNamespace

import pytest
from django.utils import timezone

from accounts.models import AccountSecurityState, EmailVerification
from organizations.authorization import (
    OperatorAuthorizationDenied,
    resolve_operator_authorization,
)
from organizations.models import Organization, OrganizationMembership

from tests.test_organization_membership import membership, verified_user


def request_for(user, generation=0):
    return SimpleNamespace(
        user=user,
        auth={
            "user_id": user.pk,
            "session_generation": generation,
            "token_type": "access",
        },
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role,permission",
    [
        (OrganizationMembership.ROLE_OWNER, "organization.ownership.manage"),
        (OrganizationMembership.ROLE_ADMINISTRATOR, "organization.settings.edit"),
        (OrganizationMembership.ROLE_MANAGER, "product_commerce.products.edit"),
        (OrganizationMembership.ROLE_STAFF, "product_commerce.products.view"),
    ],
)
def test_authorization_resolves_each_role_with_exact_permission(role, permission):
    organization = Organization.objects.create(name=f"{role} Organization")
    user = verified_user(f"authorized-{role}")
    if role != OrganizationMembership.ROLE_OWNER:
        membership(
            organization,
            verified_user(f"healthy-owner-{role}"),
            OrganizationMembership.ROLE_OWNER,
        )
    membership(organization, user, role)
    context = resolve_operator_authorization(request_for(user), organization.pk, permission)
    assert context.organization.pk == organization.pk
    assert context.membership.user_id == user.pk
    assert context.role == role
    assert permission in context.permissions
    assert isinstance(context.permissions, frozenset)


@pytest.mark.django_db
def test_authorization_fails_closed_for_unknown_permission_and_ungranted_permission():
    organization = Organization.objects.create(name="Permission Organization")
    user = verified_user("permission-user")
    membership(organization, user, OrganizationMembership.ROLE_STAFF)
    for permission in ("unknown.permission", "product_commerce.products.edit"):
        with pytest.raises(OperatorAuthorizationDenied):
            resolve_operator_authorization(request_for(user), organization.pk, permission)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "membership_status",
    [
        OrganizationMembership.STATUS_SUSPENDED,
        OrganizationMembership.STATUS_REVOKED,
    ],
)
def test_inactive_memberships_are_denied(membership_status):
    organization = Organization.objects.create(name="Inactive Membership Organization")
    user = verified_user(f"inactive-membership-{membership_status}")
    membership(organization, user, OrganizationMembership.ROLE_OWNER, membership_status)
    with pytest.raises(OperatorAuthorizationDenied):
        resolve_operator_authorization(request_for(user), organization.pk, "organization.view")


@pytest.mark.django_db
def test_inactive_user_inactive_organization_missing_membership_and_superuser_are_denied():
    organization = Organization.objects.create(name="Authorization Organization")
    inactive_user = verified_user("inactive-user", active=False)
    membership(organization, inactive_user, OrganizationMembership.ROLE_OWNER)
    with pytest.raises(OperatorAuthorizationDenied):
        resolve_operator_authorization(request_for(inactive_user), organization.pk, "organization.view")

    active_user = verified_user("active-user")
    inactive_organization = Organization.objects.create(
        name="Inactive Organization", status=Organization.STATUS_INACTIVE
    )
    membership(inactive_organization, active_user, OrganizationMembership.ROLE_OWNER)
    with pytest.raises(OperatorAuthorizationDenied):
        resolve_operator_authorization(request_for(active_user), inactive_organization.pk, "organization.view")
    with pytest.raises(OperatorAuthorizationDenied):
        resolve_operator_authorization(request_for(active_user), organization.pk, "organization.view")

    superuser = verified_user("unscoped-superuser", superuser=True)
    with pytest.raises(OperatorAuthorizationDenied):
        resolve_operator_authorization(request_for(superuser), organization.pk, "organization.view")


@pytest.mark.django_db
def test_organization_scope_isolation_and_explicit_scope():
    first = Organization.objects.create(name="First Organization")
    second = Organization.objects.create(name="Second Organization")
    user = verified_user("scoped-user")
    membership(first, verified_user("scoped-owner"), OrganizationMembership.ROLE_OWNER)
    membership(first, user, OrganizationMembership.ROLE_STAFF)
    request = request_for(user)
    assert resolve_operator_authorization(request, first.pk, "organization.view").organization.pk == first.pk
    with pytest.raises(OperatorAuthorizationDenied):
        resolve_operator_authorization(request, second.pk, "organization.view")
    with pytest.raises(OperatorAuthorizationDenied):
        resolve_operator_authorization(request, None, "organization.view")


@pytest.mark.django_db
def test_unverified_current_email_is_denied_even_when_login_verification_is_optional():
    organization = Organization.objects.create(name="Verification Organization")
    user = verified_user("unverified-user")
    membership(organization, user, OrganizationMembership.ROLE_OWNER)
    verification = EmailVerification.objects.get(user=user)
    verification.verified_at = None
    verification.save(update_fields=["verified_at", "updated_at"])
    with pytest.raises(OperatorAuthorizationDenied):
        resolve_operator_authorization(request_for(user), organization.pk, "organization.view")


@pytest.mark.django_db
def test_stale_access_token_generation_is_denied_immediately():
    organization = Organization.objects.create(name="Generation Organization")
    user = verified_user("stale-token-user")
    membership(organization, user, OrganizationMembership.ROLE_OWNER)
    AccountSecurityState.objects.create(user=user, session_generation=3)
    with pytest.raises(OperatorAuthorizationDenied):
        resolve_operator_authorization(request_for(user, generation=2), organization.pk, "organization.view")
    context = resolve_operator_authorization(request_for(user, generation=3), organization.pk, "organization.view")
    assert context.role == OrganizationMembership.ROLE_OWNER


@pytest.mark.django_db
def test_missing_security_state_uses_generation_zero_compatibility():
    organization = Organization.objects.create(name="Generation Zero Organization")
    user = verified_user("generation-zero-user")
    membership(organization, user, OrganizationMembership.ROLE_OWNER)
    assert not AccountSecurityState.objects.filter(user=user).exists()
    context = resolve_operator_authorization(request_for(user, generation=0), organization.pk, "organization.view")
    assert context.organization.pk == organization.pk
