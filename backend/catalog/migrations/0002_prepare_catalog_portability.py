import uuid
import re

from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


MAX_STOCK_QUANTITY = 2_147_483_647
SKU_PATTERN = r"[A-Z0-9][A-Z0-9._-]{0,63}\Z"


def backfill_product_identity_and_timestamps(apps, schema_editor):
    Product = apps.get_model("catalog", "Product")
    used_ids = set(
        Product.objects.exclude(portable_id__isnull=True).values_list(
            "portable_id", flat=True
        )
    )
    for product in Product.objects.filter(portable_id__isnull=True).order_by("pk"):
        portable_id = uuid.uuid4()
        while portable_id in used_ids:
            portable_id = uuid.uuid4()
        used_ids.add(portable_id)
        Product.objects.filter(pk=product.pk).update(
            portable_id=portable_id,
            updated_at=product.created_at,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0001_initial"),
        ("organizations", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="products",
                to="organizations.organization",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="portable_id",
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name="product",
            name="sku",
            field=models.CharField(
                blank=True,
                max_length=64,
                null=True,
                validators=[
                    django.core.validators.RegexValidator(
                        message="SKU must use the canonical uppercase ASCII format.",
                        regex=re.compile(SKU_PATTERN),
                    )
                ],
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="stock_quantity",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="product",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, null=True),
        ),
        migrations.RunPython(
            backfill_product_identity_and_timestamps,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="product",
            name="portable_id",
            field=models.UUIDField(editable=False, default=uuid.uuid4),
        ),
        migrations.AlterField(
            model_name="product",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
    ]
