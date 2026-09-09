import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models, transaction

from organizations.models import Organization
from catalog.portability.schema import MAX_STOCK_QUANTITY, SKU_PATTERN


def validate_portable_uuid4(value):
    if not isinstance(value, uuid.UUID) or value.version != 4:
        raise ValidationError("portable_id must be a UUIDv4.")


def validate_stock_quantity(value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError("stock_quantity must be an integer.")
    if not 0 <= value <= MAX_STOCK_QUANTITY:
        raise ValidationError(
            f"stock_quantity must be between 0 and {MAX_STOCK_QUANTITY}."
        )

# Create your models here.
class Product(models.Model):
    PRODUCT_TYPE_CHOICES = (
        ("physical", "Physical"),
        ("service", "Service"),
    )

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    product_type = models.CharField(
        max_length=20,
        choices=PRODUCT_TYPE_CHOICES,
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="products",
    )
    sku = models.CharField(
        max_length=64,
        validators=[
            RegexValidator(
                regex=SKU_PATTERN,
                message="SKU must use the canonical uppercase ASCII format.",
            )
        ],
    )
    stock_quantity = models.PositiveIntegerField(
    )
    portable_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
    )
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        if self._state.adding:
            missing = []
            if self.organization_id is None:
                missing.append("organization")
            if not self.sku:
                missing.append("sku")
            if self.stock_quantity is None:
                missing.append("stock_quantity")
            if missing:
                raise ValidationError(
                    {field: "This field is required for new Products." for field in missing}
                )
        if self.portable_id is not None:
            validate_portable_uuid4(self.portable_id)
        if self.stock_quantity is not None:
            validate_stock_quantity(self.stock_quantity)

    def save(self, *args, **kwargs):
        self.price = Decimal(str(self.price))
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "sku"),
                name="product_organization_sku_unique",
            ),
            models.UniqueConstraint(
                fields=("organization", "portable_id"),
                name="product_organization_portable_id_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(price__gte=0),
                name="product_price_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(stock_quantity__gte=0),
                name="product_stock_nonnegative",
            ),
        ]


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="images",
    )
    portable_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
    )
    storage_key = models.CharField(max_length=512)
    alt_text = models.CharField(max_length=2_000, blank=True, default="")
    sort_order = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        if self.portable_id is not None:
            validate_portable_uuid4(self.portable_id)
        if self.pk:
            existing = type(self).objects.filter(pk=self.pk).values("product_id").first()
            if existing and existing["product_id"] != self.product_id:
                raise ValidationError(
                    {"product": "ProductImage cannot be reparented."}
                )

    def save(self, *args, **kwargs):
        # The old primary must be cleared in the same transaction before the
        # conditional unique constraint can validate this new primary.
        self.full_clean(validate_constraints=False)
        with transaction.atomic():
            if self.is_primary:
                type(self).objects.filter(
                    product_id=self.product_id,
                    is_primary=True,
                ).exclude(pk=self.pk).update(is_primary=False)
            super().save(*args, **kwargs)

    class Meta:
        ordering = ("sort_order", "portable_id")
        constraints = [
            models.UniqueConstraint(
                fields=("product", "portable_id"),
                name="product_image_product_portable_id_unique",
            ),
            models.UniqueConstraint(
                fields=("product",),
                condition=models.Q(is_primary=True),
                name="product_image_one_primary_per_product",
            ),
            models.CheckConstraint(
                condition=models.Q(sort_order__gte=0),
                name="product_image_sort_order_nonnegative",
            ),
        ]
