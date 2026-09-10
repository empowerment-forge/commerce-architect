import uuid

from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0004_product_image"),
    ]

    operations = [
        migrations.CreateModel(
            name="CatalogOperationReceipt",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("operation_id", models.UUIDField(editable=False, unique=True)),
                ("operation_type", models.CharField(max_length=64)),
                ("package_sha256", models.CharField(blank=True, max_length=64, null=True)),
                ("inventory_policy", models.CharField(blank=True, max_length=32, null=True)),
                (
                    "expected_catalog_digest",
                    models.CharField(blank=True, max_length=64, null=True),
                ),
                ("pre_catalog_digest", models.CharField(blank=True, max_length=64, null=True)),
                ("post_catalog_digest", models.CharField(blank=True, max_length=64, null=True)),
                ("input_fingerprint", models.CharField(max_length=64)),
                ("result_counts", models.JSONField(default=dict)),
                ("completed_at", models.DateTimeField(default=timezone.now)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="catalog_operation_receipts",
                        to="organizations.organization",
                    ),
                ),
            ],
        ),
    ]
