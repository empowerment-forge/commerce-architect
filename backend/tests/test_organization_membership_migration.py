import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


@pytest.fixture(autouse=True)
def restore_membership_schema():
    yield
    call_command("migrate", verbosity=0)


@pytest.mark.django_db(transaction=True)
def test_membership_migration_applies_cleanly_without_seeding_rows():
    executor = MigrationExecutor(connection)
    executor.migrate([("organizations", "0001_initial")])
    executor = MigrationExecutor(connection)
    executor.migrate([("organizations", "0002_organizationmembership")])
    assert executor.loader.project_state(
        [("organizations", "0002_organizationmembership")]
    ).apps.get_model("organizations", "OrganizationMembership").objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_membership_migration_preserves_existing_organization_and_user_data():
    executor = MigrationExecutor(connection)
    executor.migrate([("organizations", "0001_initial")])
    old_apps = executor.loader.project_state(
        [("organizations", "0001_initial"), ("auth", "0012_alter_user_first_name_max_length")]
    ).apps
    OldOrganization = old_apps.get_model("organizations", "Organization")
    OldUser = old_apps.get_model("auth", "User")
    organization = OldOrganization.objects.create(name="Existing Organization")
    user = OldUser.objects.create_user(username="existing-user", email="existing@example.com")

    executor = MigrationExecutor(connection)
    executor.migrate([("organizations", "0002_organizationmembership")])
    Organization = get_user_model()._meta.apps.get_model("organizations", "Organization")
    User = get_user_model()
    assert Organization.objects.get(pk=organization.pk).name == "Existing Organization"
    assert User.objects.get(pk=user.pk).email == "existing@example.com"
