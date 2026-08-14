import uuid

import django.db.models.deletion
from django.db import migrations, models


def create_legacy_verification_records(apps, schema_editor):
    User = apps.get_model("auth", "User")
    EmailVerification = apps.get_model("accounts", "EmailVerification")
    reserved = set()
    for user in User.objects.order_by("pk").iterator():
        normalized_email = user.email.strip().casefold()
        if not normalized_email or normalized_email in reserved:
            continue
        EmailVerification.objects.create(
            user_id=user.pk,
            normalized_email=normalized_email,
        )
        reserved.add(normalized_email)


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="EmailVerification",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("normalized_email", models.EmailField(max_length=254, unique=True)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("token_digest", models.CharField(blank=True, max_length=64)),
                ("token_created_at", models.DateTimeField(blank=True, null=True)),
                ("last_sent_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="email_verification",
                        to="auth.user",
                    ),
                ),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.RunPython(
            create_legacy_verification_records,
            migrations.RunPython.noop,
        ),
    ]
