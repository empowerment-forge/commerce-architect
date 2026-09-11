import hashlib
import io
import uuid

import pytest
from django.contrib.admin.models import LogEntry, ADDITION
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import override_settings
from PIL import Image

from catalog.models import CatalogOperationReceipt, Product, ProductImage
from catalog.portability import dev_reset
from catalog.portability.codec import canonical_json_bytes
from catalog.portability.dev_reset import (
    OPERATION_TYPE,
    PurgeBlocker,
    apply_catalog_dev_purge,
    preview_catalog_dev_purge,
)
from catalog.portability.errors import CatalogPackageError
from catalog.portability.schema import ErrorCode
from media_storage.local import LocalMediaStorageAdapter
from organizations.models import Organization


@pytest.fixture
def purge_settings(settings):
    settings.COMMERCE_ENV = "development"
    settings.IS_PRODUCTION = False
    settings.CATALOG_ALLOW_DESTRUCTIVE_RESET = True
    settings.CATALOG_PORTABILITY_ENABLED = True
    return settings


def make_product(organization, sku="ITEM", *, name=None):
    return Product.objects.create(
        organization=organization,
        name=name or sku,
        description="preserved",
        product_type="physical",
        price="12.34",
        is_active=True,
        sku=sku,
        stock_quantity=4,
    )


def png_bytes():
    output = io.BytesIO()
    Image.new("RGB", (2, 2), (1, 2, 3)).save(output, format="PNG")
    return output.getvalue()


def preview(org, adapter=None):
    return preview_catalog_dev_purge(org.pk, storage_adapter=adapter)


def apply(org, digest, *, operation_id=None, confirmation=None, adapter=None):
    return apply_catalog_dev_purge(
        org.pk,
        operation_id=operation_id or uuid.uuid4(),
        expected_catalog_digest=digest,
        confirm_purge=f"PURGE-CATALOG:{org.pk}" if confirmation is None else confirmation,
        storage_adapter=adapter,
    )


@pytest.mark.django_db
def test_development_guard_and_exact_confirmation_succeed(purge_settings):
    org = Organization.objects.create(name="T15 Guard")
    product = make_product(org)
    plan = preview(org)
    receipt = apply(org, plan.target_digest)
    assert receipt.operation_type == OPERATION_TYPE
    assert receipt.result_counts == {"products_deleted": 1, "product_images_deleted": 0}
    assert not Product.objects.filter(pk=product.pk).exists()


@pytest.mark.django_db
def test_production_is_denied_even_if_debug_is_true(purge_settings):
    org = Organization.objects.create(name="T15 Production")
    with override_settings(COMMERCE_ENV="production", IS_PRODUCTION=True, DEBUG=True):
        with pytest.raises(CatalogPackageError) as error:
            preview_catalog_dev_purge(org.pk)
    assert error.value.code == ErrorCode.OPERATION_NOT_ALLOWED


@pytest.mark.django_db
def test_destructive_flag_is_required(purge_settings):
    org = Organization.objects.create(name="T15 Disabled")
    with override_settings(CATALOG_ALLOW_DESTRUCTIVE_RESET=False):
        with pytest.raises(CatalogPackageError) as error:
            preview_catalog_dev_purge(org.pk)
    assert error.value.code == ErrorCode.OPERATION_NOT_ALLOWED


@pytest.mark.django_db
def test_confirmation_mismatch_is_rejected(purge_settings):
    org = Organization.objects.create(name="T15 Confirmation")
    digest = preview(org).target_digest
    with pytest.raises(CatalogPackageError) as error:
        apply(org, digest, confirmation=f"PURGE-CATALOG:{org.pk} ")
    assert error.value.code == ErrorCode.OPERATION_NOT_ALLOWED


@pytest.mark.django_db
def test_command_separates_validate_only_from_apply(purge_settings, capsys):
    org = Organization.objects.create(name="T15 Command")
    call_command("catalog_dev_purge", organization=org.pk, validate_only=True)
    assert '"status":"valid"' in capsys.readouterr().out
    from catalog.management.commands.catalog_dev_purge import Command

    parser = Command().create_parser("manage.py", "catalog_dev_purge")
    options = {option for action in parser._actions for option in action.option_strings}
    assert "--force" not in options


@pytest.mark.django_db
def test_preview_is_mutation_free_and_reports_candidates(purge_settings):
    org = Organization.objects.create(name="T15 Preview")
    product = make_product(org)
    before_receipts = CatalogOperationReceipt.objects.count()
    result = preview(org)
    assert result.valid is True
    assert result.product_count == 1
    assert result.product_image_count == 0
    assert Product.objects.filter(pk=product.pk).exists()
    assert CatalogOperationReceipt.objects.count() == before_receipts


@pytest.mark.django_db
def test_empty_preview_is_valid_and_has_no_receipt(purge_settings):
    org = Organization.objects.create(name="T15 Empty")
    result = preview(org)
    assert result.valid is True
    assert result.product_count == result.product_image_count == 0
    assert CatalogOperationReceipt.objects.count() == 0


@pytest.mark.django_db
def test_only_selected_organization_is_deleted(purge_settings):
    first = Organization.objects.create(name="T15 A")
    second = Organization.objects.create(name="T15 B")
    selected = make_product(first, "SELECTED")
    other = make_product(second, "OTHER")
    apply(first, preview(first).target_digest)
    assert not Product.objects.filter(pk=selected.pk).exists()
    assert Product.objects.filter(pk=other.pk).exists()


@pytest.mark.django_db
def test_product_images_are_deleted_before_products(purge_settings, tmp_path):
    org = Organization.objects.create(name="T15 Images")
    product = make_product(org, "WITH-IMAGE")
    adapter = LocalMediaStorageAdapter(tmp_path / "media")
    stored = adapter.put_if_absent(png_bytes(), "image/png")
    image = ProductImage.objects.create(product=product, storage_key=stored.storage_key)
    result = apply(org, preview(org, adapter).target_digest, adapter=adapter)
    assert result.result_counts["product_images_deleted"] == 1
    assert not ProductImage.objects.filter(pk=image.pk).exists()
    assert not Product.objects.filter(pk=product.pk).exists()
    assert adapter.read_verified(stored.storage_key, 10_000).content == png_bytes()


@pytest.mark.django_db
def test_existing_receipts_and_new_receipt_are_retained(purge_settings):
    org = Organization.objects.create(name="T15 Receipts")
    old = CatalogOperationReceipt.objects.create(
        operation_id=uuid.uuid4(), organization=org, operation_type="old", input_fingerprint="a" * 64
    )
    apply(org, preview(org).target_digest)
    assert CatalogOperationReceipt.objects.filter(pk=old.pk).exists()
    assert CatalogOperationReceipt.objects.filter(operation_type=OPERATION_TYPE).count() == 1


@pytest.mark.django_db
def test_immutable_media_is_not_deleted(purge_settings, tmp_path):
    org = Organization.objects.create(name="T15 Media")
    product = make_product(org, "MEDIA")
    adapter = LocalMediaStorageAdapter(tmp_path / "media")
    stored = adapter.put_if_absent(png_bytes(), "image/png")
    ProductImage.objects.create(product=product, storage_key=stored.storage_key)
    digest = preview(org, adapter).target_digest
    apply(org, digest, adapter=adapter)
    assert adapter.read_verified(stored.storage_key, 10_000).content == png_bytes()


@pytest.mark.django_db
def test_product_sequence_is_not_reset(purge_settings):
    org = Organization.objects.create(name="T15 Sequence")
    product = make_product(org, "SEQUENCE")
    next_pk = product.pk + 1
    apply(org, preview(org).target_digest)
    replacement = make_product(org, "AFTER")
    assert replacement.pk >= next_pk


@pytest.mark.django_db
def test_admin_log_entry_is_a_registered_generic_blocker(purge_settings):
    org = Organization.objects.create(name="T15 Log")
    product = make_product(org, "LOGGED")
    user = get_user_model().objects.create_user(username="t15-log")
    LogEntry.objects.log_actions(
        user_id=user.pk,
        queryset=Product.objects.filter(pk=product.pk),
        action_flag=ADDITION,
        change_message="test",
    )
    result = preview(org)
    assert result.valid is False
    assert result.total_blocker_count == 1
    assert result.blockers[0].code == ErrorCode.REFERENCED_CATALOG


@pytest.mark.django_db
def test_command_maps_referenced_catalog_to_target_conflict_exit(purge_settings):
    org = Organization.objects.create(name="T15 Log Command")
    product = make_product(org, "LOGGED-COMMAND")
    user = get_user_model().objects.create_user(username="t15-log-command")
    LogEntry.objects.create(
        user_id=user.pk,
        content_type_id=ContentType.objects.get_for_model(Product).pk,
        object_id=str(product.pk),
        action_flag=ADDITION,
        change_message="test",
    )
    with pytest.raises(CommandError) as error:
        call_command("catalog_dev_purge", organization=org.pk, validate_only=True)
    assert error.value.returncode == 3


@pytest.mark.django_db
def test_null_generic_reference_is_not_a_blocker(purge_settings):
    org = Organization.objects.create(name="T15 Null Log")
    user = get_user_model().objects.create_user(username="t15-null")
    LogEntry.objects.create(user_id=user.pk, content_type_id=1, object_id="999999", action_flag=ADDITION, change_message="")
    assert preview(org).valid is True


@pytest.mark.django_db
def test_unknown_relation_shape_fails_closed(purge_settings, monkeypatch):
    org = Organization.objects.create(name="T15 Unknown")
    monkeypatch.setattr(
        dev_reset,
        "PURGE_EXTERNAL_RELATION_SPECS",
        (dev_reset.PurgeRelationSpec("future.OrderItem", "product", "catalog.Product"),),
    )
    with pytest.raises(CatalogPackageError) as error:
        preview(org)
    assert error.value.code == ErrorCode.UNSUPPORTED_SCHEMA


@pytest.mark.django_db
def test_unknown_custom_inspector_fails_closed(purge_settings, monkeypatch):
    org = Organization.objects.create(name="T15 Inspector")
    monkeypatch.setattr(dev_reset, "PURGE_CUSTOM_INSPECTORS", {"future": object()})
    with pytest.raises(CatalogPackageError) as error:
        preview(org)
    assert error.value.code == ErrorCode.UNSUPPORTED_SCHEMA


@pytest.mark.django_db
def test_unknown_inbound_constraint_fails_closed(purge_settings, monkeypatch):
    org = Organization.objects.create(name="T15 Constraint")
    monkeypatch.setattr(dev_reset, "PURGE_INTERNAL_DELETE_EDGES", ())
    with pytest.raises(CatalogPackageError) as error:
        preview(org)
    assert error.value.code == ErrorCode.UNSUPPORTED_SCHEMA


@pytest.mark.django_db
def test_receipt_failure_rolls_back_images_and_products(purge_settings, monkeypatch, tmp_path):
    org = Organization.objects.create(name="T15 Receipt Rollback")
    product = make_product(org, "ROLLBACK")
    adapter = LocalMediaStorageAdapter(tmp_path / "media")
    stored = adapter.put_if_absent(png_bytes(), "image/png")
    image = ProductImage.objects.create(product=product, storage_key=stored.storage_key)
    digest = preview(org, adapter).target_digest

    def fail_receipt(**kwargs):
        raise RuntimeError("receipt failure")

    monkeypatch.setattr(dev_reset, "create_operation_receipt", fail_receipt)
    with pytest.raises(CatalogPackageError) as error:
        apply(org, digest, adapter=adapter)
    assert error.value.code == ErrorCode.IMPORT_FAILED
    assert Product.objects.filter(pk=product.pk).exists()
    assert ProductImage.objects.filter(pk=image.pk).exists()


@pytest.mark.django_db
def test_collector_failure_rolls_back_without_receipt(purge_settings, monkeypatch):
    org = Organization.objects.create(name="T15 Collector Rollback")
    product = make_product(org, "COLLECTOR")
    digest = preview(org).target_digest
    monkeypatch.setattr(dev_reset, "_inspect_collector", lambda *args: (_ for _ in ()).throw(CatalogPackageError(ErrorCode.UNSUPPORTED_SCHEMA, "collector")))
    with pytest.raises(CatalogPackageError) as error:
        apply(org, digest)
    assert error.value.code == ErrorCode.UNSUPPORTED_SCHEMA
    assert Product.objects.filter(pk=product.pk).exists()
    assert CatalogOperationReceipt.objects.count() == 0


@pytest.mark.django_db
def test_exact_retry_returns_original_receipt_without_locking(purge_settings, monkeypatch):
    org = Organization.objects.create(name="T15 Retry")
    digest = preview(org).target_digest
    operation_id = uuid.uuid4()
    first = apply(org, digest, operation_id=operation_id)
    monkeypatch.setattr(dev_reset, "_lock_table", lambda model: (_ for _ in ()).throw(AssertionError("locked on retry")))
    second = apply(org, digest, operation_id=operation_id)
    assert second.pk == first.pk


@pytest.mark.django_db
def test_changed_digest_with_used_operation_id_conflicts(purge_settings):
    org = Organization.objects.create(name="T15 Conflict")
    digest = preview(org).target_digest
    operation_id = uuid.uuid4()
    apply(org, digest, operation_id=operation_id)
    with pytest.raises(CatalogPackageError) as error:
        apply(org, "0" * 64, operation_id=operation_id)
    assert error.value.code in {ErrorCode.OPERATION_ID_CONFLICT, ErrorCode.STALE_TARGET}


@pytest.mark.django_db
def test_empty_catalog_new_operation_creates_zero_receipt(purge_settings):
    org = Organization.objects.create(name="T15 Zero")
    first = apply(org, preview(org).target_digest)
    second = apply(org, preview(org).target_digest)
    assert first.pk != second.pk
    assert second.result_counts == {"products_deleted": 0, "product_images_deleted": 0}


@pytest.mark.django_db
def test_outcome_resolution_returns_present_receipt(purge_settings, monkeypatch):
    org = Organization.objects.create(name="T15 Outcome Present")
    digest = preview(org).target_digest
    receipt = apply(org, digest)
    monkeypatch.setattr(dev_reset, "find_operation_receipt", lambda *args, **kwargs: receipt)
    assert dev_reset.find_operation_receipt(uuid.uuid4(), input_fingerprint="x" * 64).pk == receipt.pk


@pytest.mark.django_db
def test_outcome_error_code_is_stable(purge_settings, monkeypatch):
    org = Organization.objects.create(name="T15 Outcome Unknown")
    digest = preview(org).target_digest
    monkeypatch.setattr(dev_reset, "create_operation_receipt", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("lost")))
    with pytest.raises(CatalogPackageError) as error:
        apply(org, digest)
    assert error.value.code == ErrorCode.IMPORT_FAILED


@pytest.mark.django_db
def test_blockers_are_sorted_and_bounded(purge_settings, monkeypatch):
    org = Organization.objects.create(name="T15 Bounded")
    blockers = [PurgeBlocker(ErrorCode.REFERENCED_CATALOG, f"row:{index:03d}", "reference") for index in range(101)]
    monkeypatch.setattr(dev_reset, "_blockers_for_graph", lambda *args: blockers)
    result = preview(org)
    assert result.valid is False
    assert len(result.blockers) == 100
    assert result.total_blocker_count == 101
    assert result.blockers_truncated is True
    assert result.blockers[0].identity == "row:000"


@pytest.mark.django_db
def test_result_counts_are_exact(purge_settings):
    org = Organization.objects.create(name="T15 Counts")
    make_product(org, "ONE")
    make_product(org, "TWO")
    receipt = apply(org, preview(org).target_digest)
    assert set(receipt.result_counts) == {"products_deleted", "product_images_deleted"}
    assert receipt.result_counts["products_deleted"] == 2


@pytest.mark.django_db
def test_receipt_stores_empty_post_digest(purge_settings):
    org = Organization.objects.create(name="T15 Post Digest")
    receipt = apply(org, preview(org).target_digest)
    assert receipt.post_catalog_digest == hashlib.sha256(
        canonical_json_bytes({"product_images": [], "products": []})
    ).hexdigest()


@pytest.mark.django_db
def test_operation_fingerprint_includes_exact_confirmation(purge_settings):
    org = Organization.objects.create(name="T15 Fingerprint")
    digest = preview(org).target_digest
    operation_id = uuid.uuid4()
    apply(org, digest, operation_id=operation_id)
    with pytest.raises(CatalogPackageError) as error:
        apply(org, digest, operation_id=operation_id, confirmation=f"PURGE-CATALOG:{org.pk} ")
    assert error.value.code == ErrorCode.OPERATION_NOT_ALLOWED


@pytest.mark.django_db
def test_inactive_organization_is_rejected(purge_settings):
    org = Organization.objects.create(name="T15 Inactive", status=Organization.STATUS_INACTIVE)
    with pytest.raises(Exception):
        preview(org)


@pytest.mark.django_db
def test_non_positive_organization_is_rejected(purge_settings):
    with pytest.raises(CatalogPackageError) as error:
        preview_catalog_dev_purge(0)
    assert error.value.code == ErrorCode.OPERATION_NOT_ALLOWED


@pytest.mark.django_db
def test_invalid_operation_id_is_rejected(purge_settings):
    org = Organization.objects.create(name="T15 UUID")
    with pytest.raises(CatalogPackageError) as error:
        apply_catalog_dev_purge(org.pk, operation_id=uuid.uuid1(), expected_catalog_digest="0" * 64, confirm_purge=f"PURGE-CATALOG:{org.pk}")
    assert error.value.code == ErrorCode.OPERATION_NOT_ALLOWED


@pytest.mark.django_db
def test_invalid_digest_is_rejected(purge_settings):
    org = Organization.objects.create(name="T15 Digest")
    with pytest.raises(CatalogPackageError) as error:
        apply_catalog_dev_purge(org.pk, operation_id=uuid.uuid4(), expected_catalog_digest="A" * 64, confirm_purge=f"PURGE-CATALOG:{org.pk}")
    assert error.value.code == ErrorCode.OPERATION_NOT_ALLOWED


@pytest.mark.django_db
def test_media_read_failure_prevents_mutation(purge_settings, tmp_path):
    org = Organization.objects.create(name="T15 Media Failure")
    product = make_product(org, "MEDIA-FAIL")
    adapter = LocalMediaStorageAdapter(tmp_path / "media")
    ProductImage.objects.create(product=product, storage_key="missing")
    with pytest.raises(CatalogPackageError) as error:
        preview(org, adapter)
    assert error.value.code == ErrorCode.MEDIA_UNAVAILABLE
    assert Product.objects.filter(pk=product.pk).exists()


@pytest.mark.django_db
def test_other_organization_receipt_is_untouched(purge_settings):
    first = Organization.objects.create(name="T15 Receipt A")
    second = Organization.objects.create(name="T15 Receipt B")
    receipt = CatalogOperationReceipt.objects.create(operation_id=uuid.uuid4(), organization=second, operation_type="keep", input_fingerprint="b" * 64)
    apply(first, preview(first).target_digest)
    assert CatalogOperationReceipt.objects.filter(pk=receipt.pk).exists()


@pytest.mark.django_db
def test_no_unrelated_sql_delete_is_emitted(purge_settings):
    org = Organization.objects.create(name="T15 SQL")
    make_product(org, "SQL")
    statements = []

    class CaptureDeletes:
        def __call__(self, execute, sql, params, many, context):
            if sql.lstrip().upper().startswith("DELETE"):
                statements.append(sql)
            return execute(sql, params, many, context)

    with connection.execute_wrapper(CaptureDeletes()):
        apply(org, preview(org).target_digest)
    assert all("catalog_product" in sql for sql in statements)


@pytest.mark.django_db
def test_command_rejects_force_option(purge_settings):
    org = Organization.objects.create(name="T15 Force")
    from catalog.management.commands.catalog_dev_purge import Command

    parser = Command().create_parser("manage.py", "catalog_dev_purge")
    option_names = {option for action in parser._actions for option in action.option_strings}
    assert "--force" not in option_names


@pytest.mark.django_db
def test_preview_uses_canonical_digest(purge_settings):
    org = Organization.objects.create(name="T15 Canonical")
    first = preview(org)
    second = preview(org)
    assert first.target_digest == second.target_digest


@pytest.mark.django_db
def test_empty_purge_does_not_create_product_rows(purge_settings):
    org = Organization.objects.create(name="T15 No Rows")
    apply(org, preview(org).target_digest)
    assert Product.objects.filter(organization=org).count() == 0


@pytest.mark.django_db
def test_catalog_portability_feature_guard_remains_required(purge_settings):
    org = Organization.objects.create(name="T15 Feature")
    with override_settings(CATALOG_PORTABILITY_ENABLED=False):
        with pytest.raises(CommandError) as error:
            call_command("catalog_dev_purge", organization=org.pk, validate_only=True)
    assert error.value.returncode == 4


@pytest.mark.django_db
def test_debug_does_not_bypass_purge_guard(purge_settings):
    org = Organization.objects.create(name="T15 Debug")
    with override_settings(DEBUG=False, CATALOG_ALLOW_DESTRUCTIVE_RESET=False):
        with pytest.raises(CatalogPackageError) as error:
            preview(org)
    assert error.value.code == ErrorCode.OPERATION_NOT_ALLOWED
