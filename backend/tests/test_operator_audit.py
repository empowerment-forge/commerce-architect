from unittest.mock import patch

import pytest
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from organizations.audit import append_audit_event
from organizations.models import Organization, OrganizationAuditEvent

from tests.test_organization_membership import verified_user


@pytest.mark.django_db
def test_audit_append_is_allowlisted_and_defaults_state():
    organization = Organization.objects.create(name="Audit Organization")
    actor = verified_user("audit-actor")

    with transaction.atomic():
        event = append_audit_event(
            organization=organization,
            actor=actor,
            action="organization.settings.updated",
            target_type="organization_settings",
            target_identifier=str(organization.pk),
        )

    assert event.outcome == "succeeded"
    assert event.before_state == {}
    assert event.after_state == {}
    assert not hasattr(event, "updated_at")


@pytest.mark.django_db
def test_audit_operation_id_is_unique_and_events_are_immutable():
    organization = Organization.objects.create(name="Audit Immutable Organization")
    actor = verified_user("audit-immutable-actor")
    with transaction.atomic():
        event = append_audit_event(
            organization=organization,
            actor=actor,
            action="organization.settings.updated",
            target_type="organization_settings",
            target_identifier="settings",
        )

    event.action = "changed"
    with pytest.raises(ValidationError):
        event.save()
    with pytest.raises(ValidationError):
        event.delete()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            append_audit_event(
                organization=organization,
                actor=actor,
                action="organization.settings.updated",
                target_type="organization_settings",
                target_identifier="settings",
                operation_id=event.operation_id,
            )


@pytest.mark.django_db
def test_audit_rejects_unsafe_state_and_requires_transaction():
    organization = Organization.objects.create(name="Audit Safety Organization")
    actor = verified_user("audit-safety-actor")
    with patch("organizations.audit.transaction.get_autocommit", return_value=True):
        with pytest.raises(RuntimeError):
            append_audit_event(
                organization=organization,
                actor=actor,
                action="organization.settings.updated",
                target_type="organization_settings",
                target_identifier="settings",
            )
    with pytest.raises(ValueError):
        with transaction.atomic():
            append_audit_event(
                organization=organization,
                actor=actor,
                action="organization.settings.updated",
                target_type="organization_settings",
                target_identifier="settings",
                after_state={"password": "do-not-store"},
            )
    with pytest.raises(ValueError):
        with transaction.atomic():
            append_audit_event(
                organization=organization,
                actor=actor,
                action="not.allowlisted",
                target_type="organization_settings",
                target_identifier="settings",
            )
    with pytest.raises(RuntimeError):
        with transaction.atomic():
            append_audit_event(
                organization=organization,
                actor=actor,
                action="organization.settings.updated",
                target_type="organization_settings",
                target_identifier="settings",
            )
            raise RuntimeError("rollback caller transaction")
    assert OrganizationAuditEvent.objects.count() == 0


@pytest.mark.django_db
def test_audit_row_is_read_only_and_active_superuser_only_in_admin():
    model_admin = admin.site._registry[OrganizationAuditEvent]
    active_superuser = verified_user("audit-admin", superuser=True)
    inactive_superuser = verified_user("inactive-audit-admin", superuser=True, active=False)
    request = type("Request", (), {"user": active_superuser})()
    inactive_request = type("Request", (), {"user": inactive_superuser})()

    assert model_admin.has_view_permission(request)
    assert not model_admin.has_add_permission(request)
    assert not model_admin.has_change_permission(request)
    assert not model_admin.has_delete_permission(request)
    assert model_admin.has_module_permission(request)
    assert not model_admin.has_view_permission(inactive_request)
    assert admin.site.is_registered(OrganizationAuditEvent)
