import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError
from django.utils import timezone

from organizations.models import Organization, OrganizationMembership
from organizations.permissions import (
    ALL_PERMISSIONS,
    ROLE_PERMISSIONS,
    has_permission,
)
from organizations.services import (
    LastActiveOwnerError,
    transition_membership,
)


def verified_user(username, *, active=True, superuser=False):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="password-for-tests",
        is_active=active,
        is_superuser=superuser,
    )
    from accounts.models import EmailVerification

    EmailVerification.objects.create(
        user=user,
        normalized_email=user.email,
        verified_at=timezone.now(),
    )
    return user


def membership(organization, user, role=OrganizationMembership.ROLE_STAFF, status=OrganizationMembership.STATUS_ACTIVE):
    return OrganizationMembership.objects.create(
        organization=organization,
        user=user,
        role=role,
        status=status,
    )


@pytest.fixture
def current_membership_schema(django_db_setup):
    """Restore the full schema after legacy migration tests target older states."""
    call_command("migrate", verbosity=0, interactive=False)


@pytest.mark.django_db
def test_membership_has_uuid_identity_no_seed_rows_and_is_not_admin_editable():
    assert OrganizationMembership.objects.count() == 0
    assert not admin.site.is_registered(OrganizationMembership)
    organization = Organization.objects.create(name="Membership Organization")
    user = verified_user("membership-user")
    record = membership(organization, user)
    assert record.pk.version == 4
    assert record.organization_id == organization.pk
    assert record.user_id == user.pk


@pytest.mark.django_db
def test_membership_ownership_is_immutable_and_pair_is_unique():
    organization = Organization.objects.create(name="Immutable Organization")
    other_organization = Organization.objects.create(name="Other Organization")
    user = verified_user("immutable-user")
    other_user = verified_user("other-user")
    record = membership(organization, user)

    record.organization = other_organization
    with pytest.raises(ValidationError):
        record.full_clean()
    record.refresh_from_db()
    record.user = other_user
    with pytest.raises(ValidationError):
        record.full_clean()

    with pytest.raises(IntegrityError):
        OrganizationMembership.objects.bulk_create([OrganizationMembership(
            organization=organization,
            user=user,
            role=OrganizationMembership.ROLE_STAFF,
            status=OrganizationMembership.STATUS_ACTIVE,
        )])


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role,expected",
    [
        (
            OrganizationMembership.ROLE_OWNER,
            ALL_PERMISSIONS,
        ),
        (
            OrganizationMembership.ROLE_ADMINISTRATOR,
            {
                "organization.view",
                "organization.settings.view",
                "organization.settings.edit",
                "organization.members.view",
                "organization.members.invite",
                "organization.members.manage",
                "organization.members.leave",
                "organization.capabilities.view",
                "organization.capabilities.manage",
                "product_commerce.products.view",
                "product_commerce.products.edit",
                "product_commerce.images.manage",
                "product_commerce.presentation.manage",
            },
        ),
        (
            OrganizationMembership.ROLE_MANAGER,
            {
                "organization.view",
                "organization.members.leave",
                "product_commerce.products.view",
                "product_commerce.products.edit",
                "product_commerce.images.manage",
            },
        ),
        (
            OrganizationMembership.ROLE_STAFF,
            {
                "organization.view",
                "organization.members.leave",
                "product_commerce.products.view",
            },
        ),
    ],
)
def test_fixed_role_permission_sets_are_exact(role, expected):
    assert ROLE_PERMISSIONS[role] == frozenset(expected)
    assert has_permission(role, "not.a.real.permission") is False


@pytest.mark.django_db
def test_invalid_role_and_status_are_rejected_by_model_validation():
    organization = Organization.objects.create(name="Validation Organization")
    user = verified_user("validation-user")
    record = OrganizationMembership(
        organization=organization,
        user=user,
        role="owner-ish",
        status="enabled",
    )
    with pytest.raises(ValidationError):
        record.full_clean()


@pytest.mark.django_db(transaction=True)
def test_last_active_owner_guard_allows_equal_owners_but_blocks_final_transition(current_membership_schema):
    organization = Organization.objects.create(name="Owner Organization")
    first = membership(organization, verified_user("owner-one"), OrganizationMembership.ROLE_OWNER)
    second = membership(organization, verified_user("owner-two"), OrganizationMembership.ROLE_OWNER)

    transition_membership(first, role=OrganizationMembership.ROLE_MANAGER)
    assert OrganizationMembership.objects.filter(
        organization=organization,
        role=OrganizationMembership.ROLE_OWNER,
        status=OrganizationMembership.STATUS_ACTIVE,
    ).count() == 1
    with pytest.raises(LastActiveOwnerError):
        transition_membership(second, role=OrganizationMembership.ROLE_MANAGER)


@pytest.mark.django_db(transaction=True)
def test_concurrent_final_owner_transitions_leave_one_healthy_owner(current_membership_schema):
    organization = Organization.objects.create(name="Concurrent Owner Organization")
    first = membership(organization, verified_user("concurrent-one"), OrganizationMembership.ROLE_OWNER)
    second = membership(organization, verified_user("concurrent-two"), OrganizationMembership.ROLE_OWNER)
    barrier = threading.Barrier(2)

    def attempt(record_id):
        from django.db import connections

        try:
            barrier.wait(timeout=5)
            transition_membership(record_id, role=OrganizationMembership.ROLE_MANAGER)
            return "succeeded"
        except LastActiveOwnerError:
            return "blocked"
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(attempt, [first.pk, second.pk]))

    assert sorted(outcomes) == ["blocked", "succeeded"]
    assert OrganizationMembership.objects.filter(
        organization=organization,
        role=OrganizationMembership.ROLE_OWNER,
        status=OrganizationMembership.STATUS_ACTIVE,
        user__is_active=True,
    ).count() == 1
