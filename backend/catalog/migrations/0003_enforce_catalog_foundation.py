from django.db import migrations, models
from django.db.models import Q
from django.core.validators import RegexValidator
import django.db.models.deletion
import re


SKU_PATTERN = r"[A-Z0-9][A-Z0-9._-]{0,63}\Z"


def assert_catalog_foundation_complete(apps, schema_editor):
    Product = apps.get_model("catalog", "Product")
    unresolved = list(
        Product.objects.filter(
            Q(organization_id__isnull=True)
            | Q(sku__isnull=True)
            | Q(stock_quantity__isnull=True)
        ).values_list("pk", flat=True)
    )
    services = list(
        Product.objects.filter(product_type="service").values_list("pk", flat=True)
    )
    negative_prices = list(
        Product.objects.filter(price__lt=0).values_list("pk", flat=True)
    )
    negative_stock = list(
        Product.objects.filter(stock_quantity__lt=0).values_list("pk", flat=True)
    )
    problems = []
    if unresolved:
        problems.append(f"incomplete Product PKs: {unresolved}")
    if services:
        problems.append(f"unsupported service Product PKs: {services}")
    if negative_prices:
        problems.append(f"negative price Product PKs: {negative_prices}")
    if negative_stock:
        problems.append(f"negative stock Product PKs: {negative_stock}")
    if problems:
        raise RuntimeError("catalog foundation is not ready: " + "; ".join(problems))


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0002_prepare_catalog_portability"),
    ]

    operations = [
        migrations.RunPython(
            assert_catalog_foundation_complete,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="product",
            name="organization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="products",
                to="organizations.organization",
            ),
        ),
        migrations.AlterField(
            model_name="product",
            name="sku",
            field=models.CharField(
                max_length=64,
                validators=[
                    RegexValidator(
                        message="SKU must use the canonical uppercase ASCII format.",
                        regex=re.compile(SKU_PATTERN),
                    )
                ],
            ),
        ),
        migrations.AlterField(
            model_name="product",
            name="stock_quantity",
            field=models.PositiveIntegerField(),
        ),
        migrations.AddConstraint(
            model_name="product",
            constraint=models.UniqueConstraint(
                fields=("organization", "sku"),
                name="product_organization_sku_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="product",
            constraint=models.UniqueConstraint(
                fields=("organization", "portable_id"),
                name="product_organization_portable_id_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="product",
            constraint=models.CheckConstraint(
                condition=models.Q(price__gte=0),
                name="product_price_nonnegative",
            ),
        ),
        migrations.AddConstraint(
            model_name="product",
            constraint=models.CheckConstraint(
                condition=models.Q(stock_quantity__gte=0),
                name="product_stock_nonnegative",
            ),
        ),
    ]
