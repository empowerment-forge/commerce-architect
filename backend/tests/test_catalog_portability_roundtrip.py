import io
import uuid

import pytest
from django.test import override_settings
from PIL import Image

from catalog.models import Product, ProductImage
from catalog.portability.codec import decode_package
from catalog.portability.exporter import build_export_package
from catalog.portability.importer import apply_catalog_import
from catalog.portability.planner import plan_catalog_import
from catalog.portability.reset import apply_storefront_reset, preview_storefront_reset
from media_storage.local import LocalMediaStorageAdapter
from organizations.models import Organization


def image_bytes():
    output = io.BytesIO()
    Image.new("RGB", (2, 2), (40, 80, 120)).save(output, format="PNG")
    return output.getvalue()


def make_product(organization, portable_id, sku, *, stock=7, active=True):
    return Product.objects.create(
        organization=organization,
        portable_id=portable_id,
        sku=sku,
        name=sku,
        description="portable description",
        product_type="physical",
        price="12.34",
        stock_quantity=stock,
        is_active=active,
    )


def apply_package(package, organization, *, adapter, mode="merge", inventory_policy="preserve"):
    plan = plan_catalog_import(
        package,
        organization.pk,
        mode=mode,
        inventory_policy=inventory_policy,
        storage_adapter=adapter,
    )
    return apply_catalog_import(
        package,
        organization.pk,
        mode=mode,
        inventory_policy=inventory_policy,
        operation_id=uuid.uuid4(),
        expected_package_sha256=plan.package_sha256,
        expected_catalog_digest=plan.target_digest,
        confirmed_organization_id=organization.pk if mode == "replace-storefront" else None,
        storage_adapter=adapter,
    )


@pytest.mark.django_db(transaction=True)
def test_soft_reset_then_replace_restore_preserves_identity_and_image_presentation(client, tmp_path):
    organization = Organization.objects.create(name="Round Trip")
    product = make_product(
        organization,
        "00000000-0000-4000-8000-000000000101",
        "ROUND-TRIP",
        stock=11,
    )
    adapter = LocalMediaStorageAdapter(tmp_path / "media")
    stored = adapter.put_if_absent(image_bytes(), "image/png")
    image = ProductImage.objects.create(
        product=product,
        storage_key=stored.storage_key,
        alt_text="Round trip image",
        sort_order=0,
        is_primary=True,
    )
    original_product_pk = product.pk
    package = build_export_package(organization.pk, storage_adapter=adapter)
    reset_preview = preview_storefront_reset(organization.pk, storage_adapter=adapter)
    apply_storefront_reset(
        organization.pk,
        operation_id=uuid.uuid4(),
        expected_catalog_digest=reset_preview.target_digest,
        confirmed_organization_id=organization.pk,
        storage_adapter=adapter,
    )

    with override_settings(
        STOREFRONT_ORGANIZATION_ID=organization.pk,
        MEDIA_PUBLIC_BASE_URL="https://media.example",
    ):
        assert client.get("/api/products/").json() == []

    apply_package(package, organization, adapter=adapter, mode="replace-storefront")
    product.refresh_from_db()
    image.refresh_from_db()

    assert product.pk == original_product_pk
    assert product.is_active is True
    assert product.stock_quantity == 11
    assert image.is_primary is True
    assert image.alt_text == "Round trip image"
    with override_settings(
        STOREFRONT_ORGANIZATION_ID=organization.pk,
        MEDIA_PUBLIC_BASE_URL="https://media.example",
    ):
        response = client.get("/api/products/")
    assert response.status_code == 200
    assert response.json()[0]["images"][0]["alt_text"] == "Round trip image"


@pytest.mark.django_db(transaction=True)
def test_fresh_organization_restore_has_canonical_content_and_new_local_pk(tmp_path):
    source = Organization.objects.create(name="Source")
    source_product = make_product(
        source,
        "00000000-0000-4000-8000-000000000102",
        "CANONICAL",
    )
    adapter = LocalMediaStorageAdapter(tmp_path / "media")
    package = build_export_package(source.pk, storage_adapter=adapter)
    destination = Organization.objects.create(name="Fresh destination")

    with override_settings(CATALOG_ALLOW_SNAPSHOT_STOCK_RESTORE=True):
        apply_package(
            package,
            destination,
            adapter=adapter,
            inventory_policy="restore-snapshot",
        )
    restored = Product.objects.get(organization=destination)
    restored_package = build_export_package(destination.pk, storage_adapter=adapter)

    assert restored.pk != source_product.pk
    assert restored.portable_id == source_product.portable_id
    assert decode_package(restored_package).catalog == decode_package(package).catalog


@pytest.mark.django_db(transaction=True)
def test_merge_preserves_destination_only_and_replace_deactivates_extras(tmp_path):
    source = Organization.objects.create(name="Merge source")
    organization = Organization.objects.create(name="Merge destination")
    make_product(
        source,
        "00000000-0000-4000-8000-000000000103",
        "INCOMING",
    )
    incoming = make_product(
        organization,
        "00000000-0000-4000-8000-000000000103",
        "INCOMING",
    )
    extra = make_product(
        organization,
        "00000000-0000-4000-8000-000000000104",
        "EXTRA",
    )
    adapter = LocalMediaStorageAdapter(tmp_path / "media")
    package = build_export_package(source.pk, storage_adapter=adapter)

    apply_package(package, organization, adapter=adapter, mode="merge")
    assert Product.objects.filter(pk=extra.pk, is_active=True).exists()

    Product.objects.filter(pk=extra.pk).update(is_active=True)
    apply_package(package, organization, adapter=adapter, mode="replace-storefront")
    assert Product.objects.filter(pk=incoming.pk, is_active=True).exists()
    assert Product.objects.filter(pk=extra.pk, is_active=False).exists()
