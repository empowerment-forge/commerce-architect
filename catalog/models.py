from django.db import models

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

    def __str__(self):
        return self.name
