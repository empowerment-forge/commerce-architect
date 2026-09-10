import pytest
from decimal import Decimal

from organizations.models import Organization
from catalog.models import Product


@pytest.mark.django_db
def test_product_model_fields_and_defaults():
    organization = Organization.objects.create(name="Test Organization")
    product = Product.objects.create(
        name="Test Product",
        description="Test description",
        product_type="physical",
        price="19.99",
        organization=organization,
        sku="TEST-001",
        stock_quantity=0,
    )

    assert product.name == "Test Product"
    assert product.price == Decimal("19.99")
    assert product.is_active is True
