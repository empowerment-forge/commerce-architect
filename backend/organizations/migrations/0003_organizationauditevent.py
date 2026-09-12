import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0002_organizationmembership"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="OrganizationAuditEvent",
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
                    "operation_id",
                    models.UUIDField(editable=False, unique=True),
                ),
                ("action", models.CharField(max_length=64)),
                ("target_type", models.CharField(max_length=64)),
                ("target_identifier", models.CharField(max_length=255)),
                (
                    "outcome",
                    models.CharField(
                        default="succeeded", editable=False, max_length=9
                    ),
                ),
                ("before_state", models.JSONField(default=dict)),
                ("after_state", models.JSONField(default=dict)),
                ("reason", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="organization_audit_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="audit_events",
                        to="organizations.organization",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="organizationauditevent",
            constraint=models.CheckConstraint(
                condition=models.Q(outcome="succeeded"),
                name="organization_audit_event_succeeded",
            ),
        ),
    ]
