import uuid

from django.core.validators import RegexValidator
from django.db import models
from django.core.exceptions import ValidationError


class Organization(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"
    STATUS_CHOICES = (
        (STATUS_ACTIVE, "Active"),
        (STATUS_INACTIVE, "Inactive"),
    )

    name = models.CharField(
        max_length=255,
        validators=[
            RegexValidator(
                regex=r"\S",
                message="Organization name must contain a non-whitespace character.",
            )
        ],
    )
    status = models.CharField(
        max_length=8,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(name__regex=r"\S"),
                name="organization_name_nonblank",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["active", "inactive"]),
                name="organization_status_valid",
            ),
        ]

    def __str__(self):
        return self.name


class OrganizationMembership(models.Model):
    ROLE_OWNER = "owner"
    ROLE_ADMINISTRATOR = "administrator"
    ROLE_MANAGER = "manager"
    ROLE_STAFF = "staff"
    ROLE_CHOICES = (
        (ROLE_OWNER, "Owner"),
        (ROLE_ADMINISTRATOR, "Administrator"),
        (ROLE_MANAGER, "Manager"),
        (ROLE_STAFF, "Staff"),
    )

    STATUS_ACTIVE = "active"
    STATUS_SUSPENDED = "suspended"
    STATUS_REVOKED = "revoked"
    STATUS_CHOICES = (
        (STATUS_ACTIVE, "Active"),
        (STATUS_SUSPENDED, "Suspended"),
        (STATUS_REVOKED, "Revoked"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="memberships",
    )
    user = models.ForeignKey(
        "auth.User",
        on_delete=models.PROTECT,
        related_name="organization_memberships",
    )
    role = models.CharField(max_length=13, choices=ROLE_CHOICES)
    status = models.CharField(max_length=9, choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "user"),
                name="organization_membership_org_user_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    role__in=[
                        "owner",
                        "administrator",
                        "manager",
                        "staff",
                    ]
                ),
                name="organization_membership_role_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    status__in=["active", "suspended", "revoked"]
                ),
                name="organization_membership_status_valid",
            ),
        ]

    def clean(self):
        super().clean()
        if self.pk and not self._state.adding:
            existing = type(self).objects.filter(pk=self.pk).values(
                "organization_id", "user_id"
            ).first()
            if existing:
                errors = {}
                if existing["organization_id"] != self.organization_id:
                    errors["organization"] = "Membership organization cannot be changed."
                if existing["user_id"] != self.user_id:
                    errors["user"] = "Membership user cannot be changed."
                if errors:
                    raise ValidationError(errors)

    def save(self, *args, **kwargs):
        transition_save = kwargs.pop("_transition_save", False)
        if self.pk and not self._state.adding and not transition_save:
            current = type(self).objects.only("role", "status").get(pk=self.pk)
            if (current.role, current.status) != (self.role, self.status):
                from .services import transition_membership

                transition_membership(self, role=self.role, status=self.status)
                return
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.organization_id}:{self.user_id}:{self.role}"


class OrganizationAuditEvent(models.Model):
    """Immutable record of a successful Organization-scoped mutation."""

    OUTCOME_SUCCEEDED = "succeeded"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="audit_events",
    )
    actor = models.ForeignKey(
        "auth.User",
        on_delete=models.PROTECT,
        related_name="organization_audit_events",
    )
    operation_id = models.UUIDField(unique=True, editable=False)
    action = models.CharField(max_length=64)
    target_type = models.CharField(max_length=64)
    target_identifier = models.CharField(max_length=255)
    outcome = models.CharField(max_length=9, default=OUTCOME_SUCCEEDED, editable=False)
    before_state = models.JSONField(default=dict)
    after_state = models.JSONField(default=dict)
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(outcome="succeeded"),
                name="organization_audit_event_succeeded",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Organization audit events are immutable.")
        self.outcome = self.OUTCOME_SUCCEEDED
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Organization audit events are immutable.")

    def __str__(self):
        return f"{self.organization_id}:{self.action}:{self.operation_id}"
