from django.core.validators import RegexValidator
from django.db import models


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
