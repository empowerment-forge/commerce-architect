"""Transactional Organization membership transitions."""

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Organization, OrganizationMembership


class LastActiveOwnerError(ValidationError):
    """The proposed transition would leave an Organization ownerless."""

    code = "last_active_owner"


def _membership_id(value):
    return getattr(value, "pk", value)


def _validate_choice(value, choices, field):
    if value not in {choice for choice, _ in choices}:
        raise ValidationError({field: f"Unsupported {field}."})


def validate_membership_transition(membership, *, role=None, status=None):
    """Lock and validate one transition; caller must already be atomic."""
    if transaction.get_autocommit():
        raise RuntimeError("membership transitions require transaction.atomic()")
    membership_id = _membership_id(membership)
    membership_owner = OrganizationMembership.objects.only("organization_id").get(
        pk=membership_id
    )
    organization = Organization.objects.select_for_update().get(
        pk=membership_owner.organization_id
    )
    locked_membership = (
        OrganizationMembership.objects.select_for_update()
        .select_related("user")
        .get(pk=membership_id, organization_id=organization.pk)
    )
    proposed_role = locked_membership.role if role is None else role
    proposed_status = locked_membership.status if status is None else status
    _validate_choice(proposed_role, OrganizationMembership.ROLE_CHOICES, "role")
    _validate_choice(proposed_status, OrganizationMembership.STATUS_CHOICES, "status")

    has_other_healthy_owner = OrganizationMembership.objects.filter(
        organization_id=organization.pk,
        role=OrganizationMembership.ROLE_OWNER,
        status=OrganizationMembership.STATUS_ACTIVE,
        user__is_active=True,
    ).exclude(pk=locked_membership.pk).exists()
    proposed_is_healthy_owner = (
        proposed_role == OrganizationMembership.ROLE_OWNER
        and proposed_status == OrganizationMembership.STATUS_ACTIVE
        and locked_membership.user.is_active
    )
    if not has_other_healthy_owner and not proposed_is_healthy_owner:
        raise LastActiveOwnerError(
            "An Organization must retain an active Owner linked to an active User."
        )
    return locked_membership, proposed_role, proposed_status


@transaction.atomic
def transition_membership(membership, *, role=None, status=None):
    """Apply one guarded role/status transition under the Organization lock."""
    locked_membership, proposed_role, proposed_status = validate_membership_transition(
        membership, role=role, status=status
    )
    locked_membership.role = proposed_role
    locked_membership.status = proposed_status
    locked_membership.save(update_fields=["role", "status", "updated_at"])
    return locked_membership
