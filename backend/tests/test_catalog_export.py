import hashlib
import io
import os

import pytest
from PIL import Image

from catalog.models import Product, ProductImage
from catalog.portability.codec import decode_package
from catalog.portability.errors import CatalogPackageError
from catalog.portability.exporter import build_export_package, export_catalog
from catalog.services import CatalogScopeError
from media_storage.local import LocalMediaStorageAdapter
from organizations.models import Organization


def image_bytes(format_name="PNG", color=(20, 40, 60)):
    output = io.BytesIO()
    image = Image.new("RGB", (2, 3), color)
    image.save(output, format=format_name)
    return output.getvalue()


def make_product(organization, *, portable_id, sku, name, active=True, stock=0):
    return Product.objects.create(
        portable_id=portable_id,
        organization=organization,
        name=name,
        description=f"Description for {name}",
        product_type="physical",
        price="12.34",
        sku=sku,
        stock_quantity=stock,
        is_active=active,
    )


def make_image(product, storage_key, *, portable_id, sort_order=0, primary=False):
    return ProductImage.objects.create(
        product=product,
        portable_id=portable_id,
        storage_key=storage_key,
        alt_text=f"Alt {product.name}",
        sort_order=sort_order,
        is_primary=primary,
    )


@pytest.mark.django_db
def test_empty_organization_exports_without_media_storage_access():
    organization = Organization.objects.create(name="Empty")

    package = decode_package(build_export_package(organization.pk))

    assert package.catalog == {"products": [], "product_images": []}
    assert package.media == {}


@pytest.mark.django_db
def test_inactive_organization_is_not_an_export_target():
    organization = Organization.objects.create(name="Inactive", status="inactive")

    with pytest.raises(CatalogScopeError):
        build_export_package(organization.pk)


@pytest.mark.django_db
def test_export_is_scoped_and_includes_active_inactive_products(tmp_path):
    organization = Organization.objects.create(name="Selected")
    other = Organization.objects.create(name="Other")
    selected = make_product(
        organization,
        portable_id="00000000-0000-4000-8000-000000000002",
        sku="SELECTED-2",
        name="Selected inactive",
        active=False,
        stock=7,
    )
    make_product(
        organization,
        portable_id="00000000-0000-4000-8000-000000000001",
        sku="SELECTED-1",
        name="Selected active",
        active=True,
    )
    make_product(
        other,
        portable_id="00000000-0000-4000-8000-000000000003",
        sku="OTHER-1",
        name="Must not export",
    )
    adapter = LocalMediaStorageAdapter(tmp_path / "media")

    package = decode_package(build_export_package(organization.pk, storage_adapter=adapter))

    assert [item["portable_id"] for item in package.catalog["products"]] == [
        "00000000-0000-4000-8000-000000000001",
        "00000000-0000-4000-8000-000000000002",
    ]
    assert package.catalog["products"][1]["status"] == "inactive"
    assert package.catalog["products"][1]["stock_quantity"] == 7
    assert all("OTHER-1" not in str(item) for item in package.catalog["products"])
    assert selected.organization_id == organization.pk


@pytest.mark.django_db
def test_export_excludes_product_images_from_other_organizations(tmp_path):
    organization = Organization.objects.create(name="Image scope")
    other = Organization.objects.create(name="Other image scope")
    selected = make_product(
        organization,
        portable_id="00000000-0000-4000-8000-000000000061",
        sku="SCOPE-1",
        name="Selected",
    )
    unrelated = make_product(
        other,
        portable_id="00000000-0000-4000-8000-000000000062",
        sku="OTHER-SCOPE-1",
        name="Unrelated",
    )
    adapter = LocalMediaStorageAdapter(tmp_path / "media")
    stored = adapter.put_if_absent(image_bytes(), "image/png")
    make_image(
        unrelated,
        stored.storage_key,
        portable_id="00000000-0000-4000-8000-000000000063",
    )

    package = decode_package(build_export_package(organization.pk, storage_adapter=adapter))

    assert package.catalog["products"] == [_product_for_assertion(selected)]
    assert package.catalog["product_images"] == []
    assert package.media == {}


def _product_for_assertion(product):
    return {
        "portable_id": str(product.portable_id),
        "sku": product.sku,
        "name": product.name,
        "description": product.description,
        "price": "12.34",
        "stock_quantity": product.stock_quantity,
        "status": "active",
    }


@pytest.mark.django_db
def test_export_embeds_verified_original_bytes_and_shared_media_once(tmp_path):
    organization = Organization.objects.create(name="Images")
    first = make_product(
        organization,
        portable_id="00000000-0000-4000-8000-000000000011",
        sku="IMAGE-1",
        name="First",
    )
    second = make_product(
        organization,
        portable_id="00000000-0000-4000-8000-000000000012",
        sku="IMAGE-2",
        name="Second",
    )
    adapter = LocalMediaStorageAdapter(tmp_path / "media")
    content = image_bytes()
    stored = adapter.put_if_absent(content, "image/png")
    make_image(
        first,
        stored.storage_key,
        portable_id="00000000-0000-4000-8000-000000000021",
        primary=True,
    )
    make_image(
        second,
        stored.storage_key,
        portable_id="00000000-0000-4000-8000-000000000022",
    )
    before_product = list(Product.objects.values_list("pk", "name", "stock_quantity", "is_active"))
    before_images = list(ProductImage.objects.values_list("pk", "storage_key", "sort_order", "is_primary"))

    package = decode_package(build_export_package(organization.pk, storage_adapter=adapter))
    expected_path = f"media/{hashlib.sha256(content).hexdigest()}.png"

    assert package.media == {expected_path: content}
    assert {item["asset_path"] for item in package.catalog["product_images"]} == {expected_path}
    assert all("sha256/" not in str(item) for item in package.catalog["product_images"])
    assert package.manifest["counts"] == {"products": 2, "product_images": 2, "media_files": 1}
    assert list(Product.objects.values_list("pk", "name", "stock_quantity", "is_active")) == before_product
    assert list(ProductImage.objects.values_list("pk", "storage_key", "sort_order", "is_primary")) == before_images
    assert adapter.read_verified(stored.storage_key, len(content)).content == content


@pytest.mark.django_db
def test_export_rejects_unsupported_service_product_without_output(tmp_path):
    organization = Organization.objects.create(name="Unsupported")
    Product.objects.create(
        organization=organization,
        name="Service",
        description="",
        product_type="service",
        price="1.00",
        sku="SERVICE-1",
        stock_quantity=0,
    )
    output = tmp_path / "catalog.ca-catalog.zip"
    adapter = LocalMediaStorageAdapter(tmp_path / "media")

    with pytest.raises(CatalogPackageError):
        export_catalog(organization.pk, output, storage_adapter=adapter)
    assert not output.exists()


@pytest.mark.django_db
def test_missing_media_fails_closed_and_preserves_existing_output(tmp_path):
    organization = Organization.objects.create(name="Missing media")
    product = make_product(
        organization,
        portable_id="00000000-0000-4000-8000-000000000031",
        sku="MISSING-1",
        name="Missing image",
    )
    make_image(
        product,
        "sha256/" + "a" * 64,
        portable_id="00000000-0000-4000-8000-000000000032",
    )
    adapter = LocalMediaStorageAdapter(tmp_path / "media")
    output = tmp_path / "catalog.ca-catalog.zip"
    output.write_bytes(b"previous export")

    with pytest.raises(CatalogPackageError) as error:
        export_catalog(organization.pk, output, storage_adapter=adapter)

    assert error.value.code.value == "MEDIA_UNAVAILABLE"
    assert output.read_bytes() == b"previous export"
    assert not list(tmp_path.glob(f".{output.name}.*.tmp"))


@pytest.mark.django_db
def test_repeated_export_is_byte_identical_and_publishes_mode_0600(tmp_path):
    organization = Organization.objects.create(name="Deterministic")
    product = make_product(
        organization,
        portable_id="00000000-0000-4000-8000-000000000041",
        sku="DETERMINISTIC-1",
        name="Deterministic",
    )
    adapter = LocalMediaStorageAdapter(tmp_path / "media")
    stored = adapter.put_if_absent(image_bytes("JPEG"), "image/jpeg")
    make_image(
        product,
        stored.storage_key,
        portable_id="00000000-0000-4000-8000-000000000042",
    )
    first_path = tmp_path / "first.zip"
    second_path = tmp_path / "second.zip"

    export_catalog(organization.pk, first_path, storage_adapter=adapter)
    export_catalog(organization.pk, second_path, storage_adapter=adapter)

    assert first_path.read_bytes() == second_path.read_bytes()
    assert os.stat(first_path).st_mode & 0o777 == 0o600
    with pytest.raises(CatalogPackageError):
        export_catalog(organization.pk, first_path, storage_adapter=adapter)


@pytest.mark.django_db
def test_writer_after_snapshot_does_not_leak_into_export(tmp_path):
    organization = Organization.objects.create(name="Snapshot")
    product = make_product(
        organization,
        portable_id="00000000-0000-4000-8000-000000000051",
        sku="SNAPSHOT-1",
        name="Before snapshot",
    )
    adapter = LocalMediaStorageAdapter(tmp_path / "media")
    stored = adapter.put_if_absent(image_bytes(), "image/png")
    make_image(
        product,
        stored.storage_key,
        portable_id="00000000-0000-4000-8000-000000000052",
    )

    class WriterAfterSnapshot:
        def __init__(self, wrapped):
            self.wrapped = wrapped
            self.written = False

        def read_verified(self, storage_key, max_bytes):
            if not self.written:
                self.written = True
                make_product(
                    organization,
                    portable_id="00000000-0000-4000-8000-000000000053",
                    sku="SNAPSHOT-2",
                    name="After snapshot",
                )
            return self.wrapped.read_verified(storage_key, max_bytes)

    package = decode_package(
        build_export_package(
            organization.pk,
            storage_adapter=WriterAfterSnapshot(adapter),
        )
    )

    assert [item["sku"] for item in package.catalog["products"]] == ["SNAPSHOT-1"]
    assert Product.objects.filter(organization=organization, sku="SNAPSHOT-2").exists()
