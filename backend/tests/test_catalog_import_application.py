import hashlib
import io
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Event

import pytest
from django.test import override_settings
from django.db import connection, connections
from django.db.migrations.executor import MigrationExecutor
from PIL import Image

from catalog.models import CatalogOperationReceipt, Product, ProductImage
from catalog.portability.codec import canonical_json_bytes, encode_package
from catalog.portability.errors import CatalogPackageError
from catalog.portability.importer import apply_catalog_import
from catalog.portability.planner import plan_catalog_import
from catalog.portability.schema import ErrorCode
from media_storage.local import LocalMediaStorageAdapter
from organizations.models import Organization


@pytest.fixture(autouse=True)
def restore_catalog_schema():
    """Migration tests earlier in the repository suite use historical schemas."""
    executor = MigrationExecutor(connection)
    executor.migrate([
        ("organizations", "0001_initial"),
        ("catalog", "0005_catalog_operation_receipt"),
    ])


def manifest_for(catalog, media=()):
    catalog_bytes = canonical_json_bytes(catalog)
    return {
        "format": "commerce-architect-catalog",
        "format_version": 1,
        "domain_schema": "product-commerce-catalog/1",
        "entity_versions": {"product": 1, "product_image": 1},
        "required_features": ["embedded-images", "organization-scope", "portable-identities", "stock-snapshot"],
        "scope": {"kind": "organization", "coverage": "full"},
        "currency": "USD",
        "inventory_semantics": "snapshot-not-reservation",
        "counts": {"products": len(catalog["products"]), "product_images": len(catalog["product_images"]), "media_files": len(media)},
        "files": [{
            "path": "catalog.json",
            "sha256": hashlib.sha256(catalog_bytes).hexdigest(),
            "size_bytes": len(catalog_bytes),
            "media_type": "application/json",
        }] + [{
            "path": path,
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
            "media_type": media_type,
        } for path, content, media_type in media],
    }


def package_for(products, images=(), media=()):
    catalog = {"products": products, "product_images": list(images)}
    return encode_package(manifest_for(catalog, media), catalog, {path: content for path, content, _ in media})


def product(portable_id, sku, *, name=None, status="active", stock=7):
    return {
        "portable_id": portable_id,
        "sku": sku,
        "name": name or sku,
        "description": "description",
        "price": "10.00",
        "stock_quantity": stock,
        "status": status,
    }


def png_bytes(color=(10, 20, 30)):
    output = io.BytesIO()
    Image.new("RGB", (2, 2), color).save(output, format="PNG")
    return output.getvalue()


def apply(package, organization, plan, *, operation_id=None, mode="merge", adapter=None, **kwargs):
    return apply_catalog_import(
        package,
        organization.pk,
        mode=mode,
        operation_id=operation_id or uuid.uuid4(),
        expected_package_sha256=plan.package_sha256,
        expected_catalog_digest=plan.target_digest,
        storage_adapter=adapter,
        **kwargs,
    )


@pytest.mark.django_db(transaction=True)
def test_apply_creates_receipt_and_preserves_stock_on_exact_retry(tmp_path):
    organization = Organization.objects.create(name="Importer")
    package = package_for([product("00000000-0000-4000-8000-000000000001", "NEW", stock=22)])
    plan = plan_catalog_import(package, organization.pk, mode="merge")
    operation_id = uuid.uuid4()
    receipt = apply_catalog_import(
        package,
        organization.pk,
        mode="merge",
        operation_id=operation_id,
        expected_package_sha256=plan.package_sha256,
        expected_catalog_digest=plan.target_digest,
        storage_adapter=LocalMediaStorageAdapter(tmp_path / "media"),
    )

    created = Product.objects.get(organization=organization)
    assert created.stock_quantity == 0
    assert receipt.operation_id == operation_id
    assert CatalogOperationReceipt.objects.count() == 1
    retried = apply_catalog_import(
        package,
        organization.pk,
        mode="merge",
        operation_id=operation_id,
        expected_package_sha256=plan.package_sha256,
        expected_catalog_digest=plan.target_digest,
        storage_adapter=LocalMediaStorageAdapter(tmp_path / "other"),
    )
    assert retried.pk == receipt.pk
    assert Product.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_changed_bytes_are_rejected_before_catalog_work():
    organization = Organization.objects.create(name="Changed")
    package = package_for([])
    with pytest.raises(CatalogPackageError) as exc:
        apply_catalog_import(
            package + b"x",
            organization.pk,
            mode="merge",
            operation_id=uuid.uuid4(),
            expected_package_sha256=hashlib.sha256(package).hexdigest(),
            expected_catalog_digest=plan_catalog_import(package, organization.pk, mode="merge").target_digest,
        )
    assert exc.value.code == ErrorCode.PACKAGE_CHANGED
    assert Product.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_product_failure_rolls_back_catalog_and_receipt(monkeypatch, tmp_path):
    organization = Organization.objects.create(name="Rollback")
    package = package_for([product("00000000-0000-4000-8000-000000000002", "ROLLBACK")])
    plan = plan_catalog_import(package, organization.pk, mode="merge")

    from catalog.portability import importer
    original = importer._apply_products

    def fail_after_apply(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("injected product failure")

    monkeypatch.setattr(importer, "_apply_products", fail_after_apply)
    with pytest.raises(CatalogPackageError) as exc:
        apply_catalog_import(
            package,
            organization.pk,
            mode="merge",
            operation_id=uuid.uuid4(),
            expected_package_sha256=plan.package_sha256,
            expected_catalog_digest=plan.target_digest,
            storage_adapter=LocalMediaStorageAdapter(tmp_path / "media"),
        )
    assert exc.value.code == ErrorCode.IMPORT_FAILED
    assert Product.objects.count() == 0
    assert CatalogOperationReceipt.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_update_noop_replace_and_exact_digest_behavior(tmp_path):
    organization = Organization.objects.create(name="Modes")
    identity = "00000000-0000-4000-8000-000000000003"
    package = package_for([product(identity, "NEW", name="Renamed", status="inactive", stock=99)])
    adapter = LocalMediaStorageAdapter(tmp_path / "media")
    plan = plan_catalog_import(package, organization.pk, mode="merge")
    first = apply(package, organization, plan, adapter=adapter)
    created = Product.objects.get(organization=organization)
    created_at, updated_at = created.created_at, created.updated_at
    assert created.name == "Renamed" and created.is_active is False and created.stock_quantity == 0
    second_plan = plan_catalog_import(package, organization.pk, mode="merge", storage_adapter=adapter)
    second = apply(package, organization, second_plan, adapter=adapter)
    created.refresh_from_db()
    assert second.post_catalog_digest == first.post_catalog_digest
    assert created.created_at == created_at and created.updated_at == updated_at
    assert CatalogOperationReceipt.objects.count() == 2


@pytest.mark.django_db(transaction=True)
def test_authoritative_images_are_created_and_empty_package_removes_them(tmp_path):
    organization = Organization.objects.create(name="Images")
    identity = "00000000-0000-4000-8000-000000000004"
    content = png_bytes()
    digest = hashlib.sha256(content).hexdigest()
    path = f"media/{digest}.png"
    image_id = "00000000-0000-4000-8000-000000000005"
    image = {"portable_id": image_id, "product_portable_id": identity, "asset_path": path, "alt_text": "cover", "sort_order": 0, "is_primary": True}
    adapter = LocalMediaStorageAdapter(tmp_path / "media")
    package = package_for([product(identity, "IMAGE")], [image], [(path, content, "image/png")])
    plan = plan_catalog_import(package, organization.pk, mode="merge", storage_adapter=adapter)
    apply(package, organization, plan, adapter=adapter)
    from catalog.models import ProductImage
    stored = ProductImage.objects.get()
    assert stored.is_primary is True and stored.storage_key == f"sha256/{digest}"
    empty = package_for([product(identity, "IMAGE")])
    empty_plan = plan_catalog_import(empty, organization.pk, mode="merge", storage_adapter=adapter)
    apply(empty, organization, empty_plan, adapter=adapter)
    assert ProductImage.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_preconditions_confirmation_and_media_failure_are_safe(tmp_path):
    organization = Organization.objects.create(name="Guards")
    package = package_for([product("00000000-0000-4000-8000-000000000006", "GUARD")])
    plan = plan_catalog_import(package, organization.pk, mode="merge")
    with pytest.raises(CatalogPackageError) as changed:
        apply_catalog_import(package + b"x", organization.pk, mode="merge", operation_id=uuid.uuid4(), expected_package_sha256=plan.package_sha256, expected_catalog_digest=plan.target_digest)
    assert changed.value.code == ErrorCode.PACKAGE_CHANGED
    with pytest.raises(CatalogPackageError) as confirmed:
        apply_catalog_import(package, organization.pk, mode="replace-storefront", operation_id=uuid.uuid4(), expected_package_sha256=plan.package_sha256, expected_catalog_digest=plan.target_digest)
    assert confirmed.value.code == ErrorCode.OPERATION_NOT_ALLOWED
    assert Product.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_replace_storefront_deactivates_only_active_destination_rows(tmp_path):
    organization = Organization.objects.create(name="Replace")
    keep_id = "00000000-0000-4000-8000-000000000007"
    drop_id = "00000000-0000-4000-8000-000000000008"
    keep = Product.objects.create(organization=organization, portable_id=keep_id, sku="KEEP", name="Keep", description="description", product_type="physical", price="10.00", stock_quantity=4)
    drop = Product.objects.create(organization=organization, portable_id=drop_id, sku="DROP", name="Drop", description="description", product_type="physical", price="10.00", stock_quantity=5)
    package = package_for([product(keep_id, "KEEP", name="Keep", stock=99)])
    plan = plan_catalog_import(package, organization.pk, mode="replace-storefront")
    receipt = apply(package, organization, plan, mode="replace-storefront", adapter=LocalMediaStorageAdapter(tmp_path / "media"), confirmed_organization_id=organization.pk)
    keep.refresh_from_db(); drop.refresh_from_db()
    assert keep.is_active is True and drop.is_active is False
    assert receipt.result_counts["deactivations"] == 1


@pytest.mark.django_db(transaction=True)
def test_stale_target_between_preflight_and_lock_is_rejected(monkeypatch, tmp_path):
    organization = Organization.objects.create(name="Stale")
    identity = "00000000-0000-4000-8000-000000000009"
    target = Product.objects.create(organization=organization, portable_id=identity, sku="STALE", name="Before", description="description", product_type="physical", price="10.00", stock_quantity=1)
    package = package_for([product(identity, "STALE", name="After")])
    plan = plan_catalog_import(package, organization.pk, mode="merge")
    from catalog.portability import importer
    original = importer._stage_media
    def stage_then_change(*args):
        result = original(*args)
        Product.objects.filter(pk=target.pk).update(name="Changed elsewhere")
        return result
    monkeypatch.setattr(importer, "_stage_media", stage_then_change)
    with pytest.raises(CatalogPackageError) as exc:
        apply(package, organization, plan, adapter=LocalMediaStorageAdapter(tmp_path / "media"))
    target.refresh_from_db()
    assert exc.value.code == ErrorCode.STALE_TARGET and target.name == "Changed elsewhere"
    assert CatalogOperationReceipt.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_image_failure_rolls_back_product_and_images(monkeypatch, tmp_path):
    organization = Organization.objects.create(name="Image rollback")
    identity = "00000000-0000-4000-8000-000000000010"
    content = png_bytes(); digest = hashlib.sha256(content).hexdigest(); path = f"media/{digest}.png"
    image = {"portable_id": "00000000-0000-4000-8000-000000000011", "product_portable_id": identity, "asset_path": path, "alt_text": "old", "sort_order": 0, "is_primary": True}
    adapter = LocalMediaStorageAdapter(tmp_path / "media")
    first_package = package_for([product(identity, "IMAGE")], [image], [(path, content, "image/png")])
    first_plan = plan_catalog_import(first_package, organization.pk, mode="merge", storage_adapter=adapter)
    apply(first_package, organization, first_plan, adapter=adapter)
    second_image = dict(image, alt_text="new")
    second_package = package_for([product(identity, "IMAGE", name="changed")], [second_image], [(path, content, "image/png")])
    second_plan = plan_catalog_import(second_package, organization.pk, mode="merge", storage_adapter=adapter)
    from catalog.portability import importer
    original = importer._apply_images
    def fail_after_images(*args):
        original(*args); raise RuntimeError("image failure")
    monkeypatch.setattr(importer, "_apply_images", fail_after_images)
    with pytest.raises(CatalogPackageError) as exc:
        apply(second_package, organization, second_plan, adapter=adapter)
    assert exc.value.code == ErrorCode.IMPORT_FAILED
    assert Product.objects.get().name == "IMAGE"
    assert ProductImage.objects.get().alt_text == "old"
    assert CatalogOperationReceipt.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_receipt_failure_rolls_back_every_catalog_write(monkeypatch, tmp_path):
    organization = Organization.objects.create(name="Receipt failure")
    package = package_for([product("00000000-0000-4000-8000-000000000012", "RECEIPT")])
    plan = plan_catalog_import(package, organization.pk, mode="merge")
    from catalog.portability import importer
    monkeypatch.setattr(importer, "create_operation_receipt", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("receipt failure")))
    with pytest.raises(CatalogPackageError) as exc:
        apply(package, organization, plan, adapter=LocalMediaStorageAdapter(tmp_path / "media"))
    assert exc.value.code == ErrorCode.IMPORT_FAILED
    assert Product.objects.count() == 0 and CatalogOperationReceipt.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_media_write_failure_mutates_no_catalog_rows(tmp_path):
    organization = Organization.objects.create(name="Media failure")
    content = png_bytes(); digest = hashlib.sha256(content).hexdigest(); path = f"media/{digest}.png"
    image = {"portable_id": "00000000-0000-4000-8000-000000000013", "product_portable_id": "00000000-0000-4000-8000-000000000014", "asset_path": path, "alt_text": "x", "sort_order": 0, "is_primary": False}
    package = package_for([product(image["product_portable_id"], "MEDIA")], [image], [(path, content, "image/png")])
    plan = plan_catalog_import(package, organization.pk, mode="merge")
    class BrokenAdapter:
        def put_if_absent(self, content, content_type):
            raise OSError("unavailable")
    with pytest.raises(CatalogPackageError) as exc:
        apply(package, organization, plan, adapter=BrokenAdapter())
    assert exc.value.code == ErrorCode.MEDIA_UNAVAILABLE
    assert Product.objects.count() == 0 and CatalogOperationReceipt.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_same_operation_id_semantic_reuse_conflicts(tmp_path):
    organization = Organization.objects.create(name="Operation conflict")
    package = package_for([product("00000000-0000-4000-8000-000000000015", "ONE")])
    plan = plan_catalog_import(package, organization.pk, mode="merge")
    operation_id = uuid.uuid4()
    apply(package, organization, plan, operation_id=operation_id, adapter=LocalMediaStorageAdapter(tmp_path / "media"))
    changed = package_for([product("00000000-0000-4000-8000-000000000015", "TWO")])
    with pytest.raises(CatalogPackageError) as exc:
        apply_catalog_import(changed, organization.pk, mode="merge", operation_id=operation_id, expected_package_sha256=hashlib.sha256(changed).hexdigest(), expected_catalog_digest=plan.target_digest)
    assert exc.value.code == ErrorCode.OPERATION_ID_CONFLICT


@pytest.mark.django_db(transaction=True)
def test_concurrent_imports_serialize_on_organization_lock(tmp_path):
    organization = Organization.objects.create(name="Concurrent")
    package = package_for([product("00000000-0000-4000-8000-000000000016", "CONCURRENT")])
    plan = plan_catalog_import(package, organization.pk, mode="merge")
    adapter = LocalMediaStorageAdapter(tmp_path / "media")

    def run():
        try:
            return apply(package, organization, plan, adapter=adapter).pk
        except CatalogPackageError as exc:
            return exc.code
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: run(), range(2)))
    assert sum(isinstance(result, int) for result in results) == 1
    assert sum(result == ErrorCode.STALE_TARGET for result in results) == 1
    assert Product.objects.filter(organization=organization).count() == 1
    assert CatalogOperationReceipt.objects.filter(organization=organization).count() == 1


@pytest.mark.django_db(transaction=True)
def test_operation_id_is_global_across_organizations(tmp_path):
    first = Organization.objects.create(name="A")
    second = Organization.objects.create(name="B")
    package = package_for([product("00000000-0000-4000-8000-000000000017", "GLOBAL")])
    first_plan = plan_catalog_import(package, first.pk, mode="merge")
    operation_id = uuid.uuid4()
    apply(package, first, first_plan, operation_id=operation_id, adapter=LocalMediaStorageAdapter(tmp_path / "a"))
    second_plan = plan_catalog_import(package, second.pk, mode="merge")
    with pytest.raises(CatalogPackageError) as exc:
        apply(package, second, second_plan, operation_id=operation_id, adapter=LocalMediaStorageAdapter(tmp_path / "b"))
    assert exc.value.code == ErrorCode.OPERATION_ID_CONFLICT
    assert Product.objects.filter(organization=second).count() == 0
    assert CatalogOperationReceipt.objects.filter(operation_id=operation_id).count() == 1


@pytest.mark.django_db(transaction=True)
def test_lock_timeout_maps_to_catalog_busy(monkeypatch, tmp_path):
    organization = Organization.objects.create(name="Busy")
    package = package_for([])
    plan = plan_catalog_import(package, organization.pk, mode="merge")
    acquired = Event()
    release = Event()

    from catalog import services
    from catalog.services import catalog_write_lock
    def hold_lock():
        try:
            with catalog_write_lock(organization.pk):
                acquired.set()
                release.wait(10)
        finally:
            connections.close_all()
    monkeypatch.setattr(services, "LOCK_TIMEOUT_SECONDS", 0.05)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(hold_lock)
        assert acquired.wait(5)
        with pytest.raises(Exception) as exc:
            apply(package, organization, plan, adapter=LocalMediaStorageAdapter(tmp_path / "media"))
        release.set()
        future.result(timeout=5)
    assert getattr(exc.value, "code", None) == "CATALOG_BUSY"


@pytest.mark.django_db(transaction=True)
def test_same_operation_id_concurrency_returns_one_immutable_receipt(tmp_path):
    organization = Organization.objects.create(name="Duplicate concurrent")
    package = package_for([product("00000000-0000-4000-8000-000000000031", "DUP")])
    plan = plan_catalog_import(package, organization.pk, mode="merge")
    operation_id = uuid.uuid4()
    adapter = LocalMediaStorageAdapter(tmp_path / "media")
    def run():
        try:
            return apply(package, organization, plan, operation_id=operation_id, adapter=adapter).pk
        except Exception as exc:
            return exc
        finally:
            connections.close_all()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: run(), range(2)))
    assert all(isinstance(result, int) for result in results)
    assert results[0] == results[1]
    assert CatalogOperationReceipt.objects.filter(operation_id=operation_id).count() == 1
    assert Product.objects.filter(organization=organization).count() == 1


@pytest.mark.django_db(transaction=True)
def test_commit_without_authoritative_receipt_is_import_failed(monkeypatch, tmp_path):
    organization = Organization.objects.create(name="Absent receipt")
    package = package_for([product("00000000-0000-4000-8000-000000000032", "ABSENT")])
    plan = plan_catalog_import(package, organization.pk, mode="merge")
    from catalog.portability import importer
    real_lock = importer.catalog_write_lock
    @contextmanager
    def commit_then_lose(organization_id):
        with real_lock(organization_id) as locked:
            yield locked
        raise RuntimeError("commit response unavailable")
    monkeypatch.setattr(importer, "catalog_write_lock", commit_then_lose)
    monkeypatch.setattr(importer, "find_operation_receipt", lambda *args, **kwargs: None)
    with pytest.raises(CatalogPackageError) as exc:
        apply(package, organization, plan, adapter=LocalMediaStorageAdapter(tmp_path / "media"))
    assert exc.value.code == ErrorCode.IMPORT_FAILED


@pytest.mark.django_db(transaction=True)
def test_lost_response_resolves_committed_receipt(monkeypatch, tmp_path):
    organization = Organization.objects.create(name="Lost response")
    package = package_for([product("00000000-0000-4000-8000-000000000018", "LOST")])
    plan = plan_catalog_import(package, organization.pk, mode="merge")
    from catalog.portability import importer
    real_lock = importer.catalog_write_lock
    @contextmanager
    def commit_then_disconnect(organization_id):
        with real_lock(organization_id) as locked:
            yield locked
        raise RuntimeError("response lost after commit")
    monkeypatch.setattr(importer, "catalog_write_lock", commit_then_disconnect)
    operation_id = uuid.uuid4()
    receipt = apply(package, organization, plan, operation_id=operation_id, adapter=LocalMediaStorageAdapter(tmp_path / "media"))
    assert receipt.operation_id == operation_id
    assert CatalogOperationReceipt.objects.filter(operation_id=operation_id).exists()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("failure_kind", ["before", "after", "constraint"])
def test_receipt_insert_failure_rolls_back_and_never_leaves_success(monkeypatch, tmp_path, failure_kind):
    organization = Organization.objects.create(name=f"Receipt {failure_kind}")
    package = package_for([product("00000000-0000-4000-8000-000000000019", "RECEIPT")])
    plan = plan_catalog_import(package, organization.pk, mode="merge")
    from catalog.portability import importer
    from django.db import IntegrityError
    original = importer.create_operation_receipt
    def fail(**kwargs):
        if failure_kind == "before":
            raise RuntimeError("before receipt")
        receipt = original(**kwargs)
        if failure_kind == "after":
            raise RuntimeError("after receipt")
        raise IntegrityError("receipt constraint")
    monkeypatch.setattr(importer, "create_operation_receipt", fail)
    with pytest.raises(CatalogPackageError) as exc:
        apply(package, organization, plan, adapter=LocalMediaStorageAdapter(tmp_path / failure_kind))
    assert exc.value.code == ErrorCode.IMPORT_FAILED
    assert Product.objects.count() == 0
    assert CatalogOperationReceipt.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_unavailable_outcome_is_reported_as_outcome_unknown(monkeypatch, tmp_path):
    organization = Organization.objects.create(name="Unknown")
    package = package_for([product("00000000-0000-4000-8000-000000000020", "UNKNOWN")])
    plan = plan_catalog_import(package, organization.pk, mode="merge")
    from catalog.portability import importer
    real_lock = importer.catalog_write_lock
    real_find = importer.find_operation_receipt
    calls = {"count": 0}
    @contextmanager
    def commit_then_fail(organization_id):
        with real_lock(organization_id) as locked:
            yield locked
        raise RuntimeError("connection lost")
    def unavailable_after_mutation(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] >= 3:
            raise OSError("database unavailable")
        return real_find(*args, **kwargs)
    monkeypatch.setattr(importer, "catalog_write_lock", commit_then_fail)
    monkeypatch.setattr(importer, "find_operation_receipt", unavailable_after_mutation)
    with pytest.raises(CatalogPackageError) as exc:
        apply(package, organization, plan, adapter=LocalMediaStorageAdapter(tmp_path / "media"))
    assert exc.value.code == ErrorCode.OUTCOME_UNKNOWN


@pytest.mark.django_db(transaction=True)
def test_restore_snapshot_guard_is_rechecked_under_lock(monkeypatch, tmp_path):
    organization = Organization.objects.create(name="Restore")
    package = package_for([product("00000000-0000-4000-8000-000000000021", "RESTORE", stock=12)])
    with override_settings(COMMERCE_ENV="development", CATALOG_ALLOW_SNAPSHOT_STOCK_RESTORE=True):
        plan = plan_catalog_import(package, organization.pk, mode="merge", inventory_policy="restore-snapshot")
        from catalog.portability import importer
        original = importer._stage_media
        def disable_after_stage(*args):
            result = original(*args)
            from django.conf import settings
            settings.CATALOG_ALLOW_SNAPSHOT_STOCK_RESTORE = False
            return result
        monkeypatch.setattr(importer, "_stage_media", disable_after_stage)
        with pytest.raises(CatalogPackageError) as exc:
            apply(package, organization, plan, adapter=LocalMediaStorageAdapter(tmp_path / "media"), inventory_policy="restore-snapshot")
    assert exc.value.code == ErrorCode.OPERATION_NOT_ALLOWED
    assert Product.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_organization_scope_keeps_colliding_catalogs_independent(tmp_path):
    first = Organization.objects.create(name="Scope A")
    second = Organization.objects.create(name="Scope B")
    identity = "00000000-0000-4000-8000-000000000022"
    Product.objects.create(organization=second, portable_id=identity, sku="SHARED", name="B", description="description", product_type="physical", price="10.00", stock_quantity=8)
    package = package_for([product(identity, "SHARED", name="A")])
    plan = plan_catalog_import(package, first.pk, mode="merge")
    apply(package, first, plan, adapter=LocalMediaStorageAdapter(tmp_path / "media"))
    assert Product.objects.get(organization=second).name == "B"
    assert Product.objects.filter(organization=first).count() == 1
    assert CatalogOperationReceipt.objects.filter(organization=second).count() == 0


@pytest.mark.django_db(transaction=True)
def test_primary_transition_failure_restores_original_aggregate(monkeypatch, tmp_path):
    organization = Organization.objects.create(name="Primary rollback")
    identity = "00000000-0000-4000-8000-000000000023"
    old_content = png_bytes(); old_digest = hashlib.sha256(old_content).hexdigest(); old_path = f"media/{old_digest}.png"
    old_image = {"portable_id": "00000000-0000-4000-8000-000000000024", "product_portable_id": identity, "asset_path": old_path, "alt_text": "old", "sort_order": 0, "is_primary": True}
    adapter = LocalMediaStorageAdapter(tmp_path / "media")
    initial = package_for([product(identity, "PRIMARY")], [old_image], [(old_path, old_content, "image/png")])
    initial_plan = plan_catalog_import(initial, organization.pk, mode="merge", storage_adapter=adapter)
    apply(initial, organization, initial_plan, adapter=adapter)
    new_content = png_bytes((80, 70, 60)); new_digest = hashlib.sha256(new_content).hexdigest(); new_path = f"media/{new_digest}.png"
    new_image = {"portable_id": "00000000-0000-4000-8000-000000000025", "product_portable_id": identity, "asset_path": new_path, "alt_text": "new", "sort_order": 0, "is_primary": True}
    replacement = package_for([product(identity, "PRIMARY")], [new_image], [(new_path, new_content, "image/png")])
    replacement_plan = plan_catalog_import(replacement, organization.pk, mode="merge", storage_adapter=adapter)
    from catalog.portability import importer
    original = importer._apply_images
    def fail_after_transition(*args):
        original(*args); raise RuntimeError("primary transition failure")
    monkeypatch.setattr(importer, "_apply_images", fail_after_transition)
    with pytest.raises(CatalogPackageError) as exc:
        apply(replacement, organization, replacement_plan, adapter=adapter)
    assert exc.value.code == ErrorCode.IMPORT_FAILED
    restored = ProductImage.objects.get()
    assert str(restored.portable_id) == old_image["portable_id"] and restored.is_primary is True


@pytest.mark.django_db(transaction=True)
def test_verified_media_readback_mismatch_is_media_unavailable(tmp_path):
    organization = Organization.objects.create(name="Readback")
    content = png_bytes(); digest = hashlib.sha256(content).hexdigest(); path = f"media/{digest}.png"
    image = {"portable_id": "00000000-0000-4000-8000-000000000026", "product_portable_id": "00000000-0000-4000-8000-000000000027", "asset_path": path, "alt_text": "x", "sort_order": 0, "is_primary": False}
    package = package_for([product(image["product_portable_id"], "READBACK")], [image], [(path, content, "image/png")])
    plan = plan_catalog_import(package, organization.pk, mode="merge")
    from media_storage.contracts import StoredMedia
    class MismatchAdapter:
        def put_if_absent(self, content, content_type):
            return StoredMedia("sha256/" + "0" * 64, "0" * 64, len(content), content_type)
    with pytest.raises(CatalogPackageError) as exc:
        apply(package, organization, plan, adapter=MismatchAdapter())
    assert exc.value.code == ErrorCode.MEDIA_UNAVAILABLE
    assert Product.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_final_state_divergence_rolls_back(monkeypatch, tmp_path):
    organization = Organization.objects.create(name="Divergence")
    identity = "00000000-0000-4000-8000-000000000028"
    package = package_for([product(identity, "DIVERGE")])
    plan = plan_catalog_import(package, organization.pk, mode="merge")
    from catalog.portability import importer
    original = importer._apply_products
    def diverge(*args, **kwargs):
        result = original(*args, **kwargs)
        Product.objects.filter(organization=organization).update(name="unexpected")
        return result
    monkeypatch.setattr(importer, "_apply_products", diverge)
    with pytest.raises(CatalogPackageError) as exc:
        apply(package, organization, plan, adapter=LocalMediaStorageAdapter(tmp_path / "media"))
    assert exc.value.code == ErrorCode.IMPORT_FAILED
    assert Product.objects.count() == 0 and CatalogOperationReceipt.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_concurrent_different_organizations_are_isolated(tmp_path):
    first = Organization.objects.create(name="Concurrent A")
    second = Organization.objects.create(name="Concurrent B")
    package_a = package_for([product("00000000-0000-4000-8000-000000000029", "A")])
    package_b = package_for([product("00000000-0000-4000-8000-000000000030", "B")])
    plan_a = plan_catalog_import(package_a, first.pk, mode="merge")
    plan_b = plan_catalog_import(package_b, second.pk, mode="merge")
    adapter = LocalMediaStorageAdapter(tmp_path / "media")
    def run(args):
        package, organization, plan = args
        try:
            return apply(package, organization, plan, adapter=adapter).organization_id
        finally:
            connections.close_all()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, [(package_a, first, plan_a), (package_b, second, plan_b)]))
    assert set(results) == {first.pk, second.pk}
    assert Product.objects.filter(organization=first).count() == 1
    assert Product.objects.filter(organization=second).count() == 1
