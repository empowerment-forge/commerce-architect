import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="OrganizationMembership",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("owner", "Owner"),
                            ("administrator", "Administrator"),
                            ("manager", "Manager"),
                            ("staff", "Staff"),
                        ],
                        max_length=13,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("suspended", "Suspended"),
                            ("revoked", "Revoked"),
                        ],
                        max_length=9,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="memberships",
                        to="organizations.organization",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="organization_memberships",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="organizationmembership",
            constraint=models.UniqueConstraint(
                fields=("organization", "user"),
                name="organization_membership_org_user_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="organizationmembership",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    role__in=["owner", "administrator", "manager", "staff"]
                ),
                name="organization_membership_role_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="organizationmembership",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    status__in=["active", "suspended", "revoked"]
                ),
                name="organization_membership_status_valid",
            ),
        ),
    ]
