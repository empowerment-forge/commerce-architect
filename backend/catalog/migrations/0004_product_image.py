import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0003_enforce_catalog_foundation"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductImage",
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
                (
                    "portable_id",
                    models.UUIDField(default=uuid.uuid4, editable=False),
                ),
                ("storage_key", models.CharField(max_length=512)),
                (
                    "alt_text",
                    models.CharField(blank=True, default="", max_length=2000),
                ),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("is_primary", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="images",
                        to="catalog.product",
                    ),
                ),
            ],
            options={"ordering": ("sort_order", "portable_id")},
        ),
        migrations.AddConstraint(
            model_name="productimage",
            constraint=models.UniqueConstraint(
                fields=("product", "portable_id"),
                name="product_image_product_portable_id_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="productimage",
            constraint=models.UniqueConstraint(
                condition=models.Q(is_primary=True),
                fields=("product",),
                name="product_image_one_primary_per_product",
            ),
        ),
        migrations.AddConstraint(
            model_name="productimage",
            constraint=models.CheckConstraint(
                condition=models.Q(sort_order__gte=0),
                name="product_image_sort_order_nonnegative",
            ),
        ),
    ]
