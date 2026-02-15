import pytest
from decimal import Decimal

from catalog.models import Product


@pytest.mark.django_db
def test_product_model_fields_and_defaults():
    product = Product.objects.create(
        name="Test Product",
        description="Test description",
        product_type="physical",
        price="19.99",
    )

    assert product.name == "Test Product"
    assert product.price == Decimal("19.99")
    assert product.is_active is True
