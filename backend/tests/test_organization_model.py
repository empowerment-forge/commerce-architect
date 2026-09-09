import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import RequestFactory, override_settings

from organizations.admin import OrganizationAdmin
from organizations.models import Organization


@pytest.fixture
def organization_admin():
    return OrganizationAdmin(Organization, AdminSite())


@pytest.fixture
def request_factory():
    return RequestFactory()


def request_for_user(request_factory, user):
    request = request_factory.get("/admin/")
    request.user = user
    return request


@pytest.mark.django_db
def test_organization_requires_nonblank_name():
    for name in ("", "   ", "\t\n"):
        organization = Organization(name=name)
        with pytest.raises(ValidationError):
            organization.full_clean()


@pytest.mark.django_db
@pytest.mark.parametrize("status", [Organization.STATUS_ACTIVE, Organization.STATUS_INACTIVE])
def test_organization_accepts_only_specified_status_values(status):
    organization = Organization(name="Example Organization", status=status)
    organization.full_clean()
    organization.save()
    assert organization.status == status


@pytest.mark.django_db
def test_organization_rejects_unknown_status():
    with pytest.raises(ValidationError):
        Organization(name="Example Organization", status="pending").full_clean()


@pytest.mark.django_db
def test_organization_migration_does_not_seed_data():
    assert Organization.objects.count() == 0


@pytest.mark.django_db
def test_organization_admin_is_restricted_to_active_superusers(
    organization_admin, request_factory
):
    user_model = get_user_model()
    regular_staff = user_model.objects.create_user(
        username="organization-staff",
        password="test-password",
        is_staff=True,
        is_active=True,
    )
    inactive_superuser = user_model.objects.create_superuser(
        username="inactive-superuser",
        password="test-password",
    )
    inactive_superuser.is_active = False
    inactive_superuser.save(update_fields=["is_active"])
    active_superuser = user_model.objects.create_superuser(
        username="active-superuser",
        password="test-password",
    )

    for user in (regular_staff, inactive_superuser):
        request = request_for_user(request_factory, user)
        assert organization_admin.has_module_permission(request) is False
        assert organization_admin.has_view_permission(request) is False
        assert organization_admin.has_add_permission(request) is False
        assert organization_admin.has_change_permission(request) is False
        assert organization_admin.has_delete_permission(request) is False

    request = request_for_user(request_factory, active_superuser)
    assert organization_admin.has_module_permission(request) is True
    assert organization_admin.has_view_permission(request) is True
    assert organization_admin.has_add_permission(request) is True
    assert organization_admin.has_change_permission(request) is True
    assert organization_admin.has_delete_permission(request) is True


@pytest.mark.django_db
@override_settings(
    STOREFRONT_ORGANIZATION_ID=None,
    CATALOG_PORTABILITY_ENABLED=False,
)
def test_missing_storefront_configuration_does_not_select_an_organization():
    Organization.objects.create(name="Unselected Organization")
    from django.conf import settings

    assert settings.STOREFRONT_ORGANIZATION_ID is None
    assert settings.CATALOG_PORTABILITY_ENABLED is False
