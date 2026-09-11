import io
import uuid

import pytest
from django.db import connection
from PIL import Image

from catalog.models import CatalogOperationReceipt, Product, ProductImage
from catalog.portability.errors import CatalogPackageError
from catalog.portability.reset import apply_storefront_reset, preview_storefront_reset
from catalog.portability.schema import ErrorCode
from media_storage.local import LocalMediaStorageAdapter
from organizations.models import Organization


def png_bytes():
    output = io.BytesIO()
    Image.new("RGB", (2, 2), (10, 20, 30)).save(output, format="PNG")
    return output.getvalue()


def make_product(organization, sku, *, active=True, stock=0):
    return Product.objects.create(
        organization=organization,
        name=sku,
        description="unchanged description",
        product_type="physical",
        price="10.00",
        is_active=active,
        sku=sku,
        stock_quantity=stock,
    )


def reset(organization, digest, *, operation_id=None, adapter=None, confirmation=None):
    return apply_storefront_reset(
        organization.pk,
        operation_id=operation_id or uuid.uuid4(),
        expected_catalog_digest=digest,
        confirmed_organization_id=organization.pk if confirmation is None else confirmation,
        storage_adapter=adapter,
    )


@pytest.mark.django_db
def test_reset_deactivates_only_active_rows_and_preserves_catalog_data(tmp_path):
    first = Organization.objects.create(name="Reset A")
    second = Organization.objects.create(name="Reset B")
    active = make_product(first, "ACTIVE", active=True, stock=7)
    inactive = make_product(first, "INACTIVE", active=False, stock=8)
    other = make_product(second, "OTHER", active=True, stock=9)
    adapter = LocalMediaStorageAdapter(tmp_path / "media")
    stored = adapter.put_if_absent(png_bytes(), "image/png")
    image = ProductImage.objects.create(
        product=active,
        storage_key=stored.storage_key,
        alt_text="keep me",
        sort_order=3,
        is_primary=True,
    )
    before = {
        product.pk: {
            "portable_id": product.portable_id,
            "name": product.name,
            "description": product.description,
            "price": product.price,
            "stock_quantity": product.stock_quantity,
            "created_at": product.created_at,
            "updated_at": product.updated_at,
        }
        for product in (active, inactive, other)
    }
    preview = preview_storefront_reset(first.pk, storage_adapter=adapter)

    receipt = reset(first, preview.target_digest, adapter=adapter)

    active.refresh_from_db()
    inactive.refresh_from_db()
    other.refresh_from_db()
    image.refresh_from_db()
    assert receipt.result_counts == {"deactivations": 1}
    assert active.is_active is False
    assert inactive.is_active is False
    assert other.is_active is True
    for product in (active, inactive, other):
        original = before[product.pk]
        assert product.portable_id == original["portable_id"]
        assert product.name == original["name"]
        assert product.description == original["description"]
        assert product.price == original["price"]
        assert product.stock_quantity == original["stock_quantity"]
        assert product.created_at == original["created_at"]
    assert inactive.updated_at == before[inactive.pk]["updated_at"]
    assert other.updated_at == before[other.pk]["updated_at"]
    assert active.updated_at > before[active.pk]["updated_at"]
    assert image.storage_key == stored.storage_key
    assert image.alt_text == "keep me"
    assert image.sort_order == 3
    assert image.is_primary is True


@pytest.mark.django_db
def test_preview_is_mutation_free_and_empty_reset_is_idempotent():
    organization = Organization.objects.create(name="Empty Reset")
    preview = preview_storefront_reset(organization.pk)
    assert preview.deactivations == 0
    assert Product.objects.count() == 0
    operation_id = uuid.uuid4()

    first = reset(organization, preview.target_digest, operation_id=operation_id)
    second = reset(organization, preview.target_digest, operation_id=operation_id)

    assert first.pk == second.pk
    assert first.result_counts == {"deactivations": 0}
    assert CatalogOperationReceipt.objects.count() == 1


@pytest.mark.django_db
def test_reset_requires_confirmation_and_rejects_stale_preview():
    organization = Organization.objects.create(name="Guarded Reset")
    product = make_product(organization, "GUARDED")
    preview = preview_storefront_reset(organization.pk)
    with pytest.raises(CatalogPackageError) as confirmation_error:
        apply_storefront_reset(
            organization.pk,
            operation_id=uuid.uuid4(),
            expected_catalog_digest=preview.target_digest,
            confirmed_organization_id=organization.pk + 1,
        )
    assert confirmation_error.value.code == ErrorCode.OPERATION_NOT_ALLOWED

    Product.objects.filter(pk=product.pk).update(name="changed")
    with pytest.raises(CatalogPackageError) as stale_error:
        reset(organization, preview.target_digest)
    assert stale_error.value.code == ErrorCode.STALE_TARGET
    product.refresh_from_db()
    assert product.is_active is True


@pytest.mark.django_db
def test_injected_receipt_failure_rolls_back_product_state(monkeypatch):
    organization = Organization.objects.create(name="Rollback Reset")
    product = make_product(organization, "ROLLBACK")
    preview = preview_storefront_reset(organization.pk)

    def fail_receipt(**kwargs):
        raise RuntimeError("receipt insert failed")

    monkeypatch.setattr("catalog.portability.reset.create_operation_receipt", fail_receipt)
    with pytest.raises(CatalogPackageError) as error:
        reset(organization, preview.target_digest)
    assert error.value.code == ErrorCode.IMPORT_FAILED
    product.refresh_from_db()
    assert product.is_active is True
    assert CatalogOperationReceipt.objects.count() == 0


@pytest.mark.django_db
def test_reset_emits_no_delete_statements(monkeypatch):
    organization = Organization.objects.create(name="No Deletes")
    make_product(organization, "NO-DELETE")
    preview = preview_storefront_reset(organization.pk)
    statements = []

    class CaptureDeletes:
        def __call__(self, execute, sql, params, many, context):
            if sql.lstrip().upper().startswith("DELETE"):
                statements.append(sql)
            return execute(sql, params, many, context)

    with connection.execute_wrapper(CaptureDeletes()):
        reset(organization, preview.target_digest)
    assert statements == []
