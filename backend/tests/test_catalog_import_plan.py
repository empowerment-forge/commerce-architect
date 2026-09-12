import hashlib
import io

import pytest
from django.test import override_settings
from PIL import Image

from catalog.models import Product, ProductImage
from catalog.portability.codec import canonical_json_bytes, encode_package
from catalog.portability.errors import CatalogPackageError
from catalog.portability.planner import plan_catalog_import
from catalog.portability.schema import ErrorCode
from media_storage.local import LocalMediaStorageAdapter
from organizations.models import Organization


def product(portable_id, sku, *, name=None, status="active", stock=0):
    return {
        "portable_id": portable_id,
        "sku": sku,
        "name": name or sku,
        "description": "description",
        "price": "10.00",
        "stock_quantity": stock,
        "status": status,
    }


def manifest_for(catalog, media):
    catalog_bytes = canonical_json_bytes(catalog)
    files = [{
        "path": "catalog.json",
        "sha256": hashlib.sha256(catalog_bytes).hexdigest(),
        "size_bytes": len(catalog_bytes),
        "media_type": "application/json",
    }]
    for path, content, media_type in media:
        files.append({
            "path": path,
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
            "media_type": media_type,
        })
    return {
        "format": "commerce-architect-catalog",
        "format_version": 1,
        "domain_schema": "product-commerce-catalog/1",
        "entity_versions": {"product": 1, "product_image": 1},
        "required_features": ["embedded-images", "organization-scope", "portable-identities", "stock-snapshot"],
        "scope": {"kind": "organization", "coverage": "full"},
        "currency": "USD",
        "inventory_semantics": "snapshot-not-reservation",
        "counts": {
            "products": len(catalog["products"]),
            "product_images": len(catalog["product_images"]),
            "media_files": len(media),
        },
        "files": files,
    }


def package_for(products, images=None, media=()):
    catalog = {"products": products, "product_images": images or []}
    media_mapping = {path: content for path, content, _ in media}
    return encode_package(manifest_for(catalog, media), catalog, media_mapping)


def png_bytes(color=(10, 20, 30)):
    output = io.BytesIO()
    Image.new("RGB", (2, 2), color).save(output, format="PNG")
    return output.getvalue()


def make_target(organization, portable_id, sku, *, active=True, stock=0, name=None):
    return Product.objects.create(
        organization=organization,
        portable_id=portable_id,
        sku=sku,
        name=name or sku,
        description="description",
        product_type="physical",
        price="10.00",
        is_active=active,
        stock_quantity=stock,
    )


@pytest.mark.django_db
def test_plan_create_update_noop_and_preserve_stock():
    organization = Organization.objects.create(name="Target")
    existing = make_target(
        organization,
        "00000000-0000-4000-8000-000000000001",
        "EXISTING",
        stock=9,
    )
    incoming = [
        product(str(existing.portable_id), "EXISTING", name="Changed", stock=22),
        product("00000000-0000-4000-8000-000000000002", "NEW", stock=8),
    ]

    plan = plan_catalog_import(
        package_for(incoming),
        organization.pk,
        mode="merge",
        inventory_policy="preserve",
    )

    assert plan.valid
    assert plan.counts == {"creates": 1, "updates": 1, "no_ops": 0, "removals": 0, "deactivations": 0}
    actions = {action.product_portable_id: action for action in plan.actions if action.image_portable_id is None}
    assert actions[str(existing.portable_id)].changes == {"name": "Changed"}
    assert actions[str(existing.portable_id)].stock_preserved is True
    assert actions["00000000-0000-4000-8000-000000000002"].changes["stock_quantity"] == 0
    assert Product.objects.get(pk=existing.pk).stock_quantity == 9


@pytest.mark.django_db
def test_same_values_are_noop_and_target_digest_is_stable():
    organization = Organization.objects.create(name="Stable")
    existing = make_target(
        organization,
        "00000000-0000-4000-8000-000000000011",
        "STABLE",
        stock=3,
    )
    package = package_for([product(str(existing.portable_id), "STABLE", stock=999)])

    first = plan_catalog_import(package, organization.pk, mode="merge")
    second = plan_catalog_import(package, organization.pk, mode="merge")

    assert first.target_digest == second.target_digest
    assert first.package_sha256 == second.package_sha256
    assert first.counts["no_ops"] == 1
    assert first.actions[0].changes == {}
    assert Product.objects.get(pk=existing.pk).stock_quantity == 3


@pytest.mark.django_db
def test_changed_sku_is_safe_but_inactive_sku_conflict_is_rejected():
    organization = Organization.objects.create(name="SKU")
    first = make_target(
        organization,
        "00000000-0000-4000-8000-000000000021",
        "FIRST",
    )
    second = make_target(
        organization,
        "00000000-0000-4000-8000-000000000022",
        "TAKEN",
        active=False,
    )
    safe = plan_catalog_import(
        package_for([product(str(first.portable_id), "CHANGED")]),
        organization.pk,
        mode="merge",
    )
    conflict = plan_catalog_import(
        package_for([product(str(first.portable_id), "TAKEN")]),
        organization.pk,
        mode="merge",
    )

    assert safe.valid
    assert safe.actions[0].changes == {"sku": "CHANGED", "name": "CHANGED"}
    assert not conflict.valid
    assert conflict.errors[0].code == ErrorCode.SKU_CONFLICT
    assert second.is_active is False


@pytest.mark.django_db
def test_merge_preserves_absent_products_and_replace_deactivates_only_active_rows():
    organization = Organization.objects.create(name="Modes")
    active = make_target(
        organization,
        "00000000-0000-4000-8000-000000000031",
        "ACTIVE",
        active=True,
    )
    inactive = make_target(
        organization,
        "00000000-0000-4000-8000-000000000032",
        "INACTIVE",
        active=False,
    )
    package = package_for([])

    merge = plan_catalog_import(package, organization.pk, mode="merge")
    replace = plan_catalog_import(package, organization.pk, mode="replace-storefront")

    assert merge.counts["deactivations"] == 0
    assert replace.counts["deactivations"] == 1
    assert replace.actions[0].product_portable_id == str(active.portable_id)
    assert inactive.is_active is False


@pytest.mark.django_db
def test_image_collection_is_authoritative_and_content_changes_are_planned(tmp_path):
    organization = Organization.objects.create(name="Images")
    target = make_target(
        organization,
        "00000000-0000-4000-8000-000000000041",
        "IMAGE",
    )
    adapter = LocalMediaStorageAdapter(tmp_path / "media")
    old_content = png_bytes()
    new_content = png_bytes((90, 80, 70))
    old = adapter.put_if_absent(old_content, "image/png")
    new = adapter.put_if_absent(new_content, "image/png")
    ProductImage.objects.create(
        product=target,
        portable_id="00000000-0000-4000-8000-000000000042",
        storage_key=old.storage_key,
        alt_text="old",
        sort_order=0,
    )
    package = package_for(
        [product(str(target.portable_id), "IMAGE")],
        [{
            "portable_id": "00000000-0000-4000-8000-000000000043",
            "product_portable_id": str(target.portable_id),
            "asset_path": f"media/{new.sha256}.png",
            "alt_text": "new",
            "sort_order": 1,
            "is_primary": True,
        }],
        [(f"media/{new.sha256}.png", new_content, "image/png")],
    )

    plan = plan_catalog_import(package, organization.pk, mode="merge", storage_adapter=adapter)
    kinds = {action.kind for action in plan.actions}

    assert plan.valid
    assert plan.counts["creates"] == 1
    assert "create-image" in kinds
    assert "remove-image" in kinds
    assert all(ProductImage.objects.filter(product=target).values_list("storage_key", flat=True))


@pytest.mark.django_db
def test_restore_snapshot_requires_development_flag_and_applies_planned_stock():
    organization = Organization.objects.create(name="Stock")
    target = make_target(
        organization,
        "00000000-0000-4000-8000-000000000051",
        "STOCK",
        stock=2,
    )
    package = package_for([product(str(target.portable_id), "STOCK", stock=8)])

    with pytest.raises(CatalogPackageError) as disabled:
        plan_catalog_import(package, organization.pk, mode="merge", inventory_policy="restore-snapshot")
    with override_settings(
        COMMERCE_ENV="development",
        CATALOG_ALLOW_SNAPSHOT_STOCK_RESTORE=True,
    ):
        plan = plan_catalog_import(
            package,
            organization.pk,
            mode="merge",
            inventory_policy="restore-snapshot",
        )

    assert disabled.value.code == ErrorCode.OPERATION_NOT_ALLOWED
    assert plan.actions[0].changes == {"stock_quantity": 8}
    assert Product.objects.get(pk=target.pk).stock_quantity == 2


@pytest.mark.django_db
def test_same_uuid_and_sku_are_isolated_between_organizations():
    first = Organization.objects.create(name="A")
    second = Organization.objects.create(name="B")
    portable_id = "00000000-0000-4000-8000-000000000061"
    make_target(first, portable_id, "SHARED")

    plan = plan_catalog_import(
        package_for([product(portable_id, "SHARED")]),
        second.pk,
        mode="merge",
    )

    assert plan.valid
    assert plan.counts["creates"] == 1
    assert Product.objects.filter(organization=first).count() == 1
    assert Product.objects.filter(organization=second).count() == 0


@pytest.mark.django_db
def test_duplicate_product_sku_errors_are_sorted_and_bounded():
    organization = Organization.objects.create(name="Errors")
    products = [
        product(
            f"00000000-0000-4000-8000-{index:012d}",
            "DUPLICATE",
        )
        for index in range(102)
    ]

    plan = plan_catalog_import(package_for(products), organization.pk, mode="merge")

    assert not plan.valid
    assert plan.total_error_count == 101
    assert plan.errors_truncated is True
    assert len(plan.errors) == 100
    assert all(error.code == ErrorCode.DUPLICATE_SKU for error in plan.errors)
