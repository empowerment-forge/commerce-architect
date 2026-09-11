import hashlib
import json
import uuid

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from catalog.models import CatalogOperationReceipt, Product
from catalog.portability.codec import canonical_json_bytes, encode_package
from media_storage.configuration import get_media_storage
from organizations.models import Organization


def package_for(products=None):
    catalog = {"products": products or [], "product_images": []}
    catalog_bytes = canonical_json_bytes(catalog)
    manifest = {
        "format": "commerce-architect-catalog",
        "format_version": 1,
        "domain_schema": "product-commerce-catalog/1",
        "entity_versions": {"product": 1, "product_image": 1},
        "required_features": ["embedded-images", "organization-scope", "portable-identities", "stock-snapshot"],
        "scope": {"kind": "organization", "coverage": "full"},
        "currency": "USD",
        "inventory_semantics": "snapshot-not-reservation",
        "counts": {"products": len(catalog["products"]), "product_images": 0, "media_files": 0},
        "files": [{
            "path": "catalog.json",
            "sha256": hashlib.sha256(catalog_bytes).hexdigest(),
            "size_bytes": len(catalog_bytes),
            "media_type": "application/json",
        }],
    }
    return encode_package(manifest, catalog, {})


def product_row(portable_id, sku):
    return {
        "portable_id": portable_id,
        "sku": sku,
        "name": sku,
        "description": "description",
        "price": "10.00",
        "stock_quantity": 0,
        "status": "active",
    }


@pytest.fixture
def portability_enabled(settings):
    settings.CATALOG_PORTABILITY_ENABLED = True


@pytest.mark.django_db
def test_export_requires_organization_and_output(portability_enabled):
    with pytest.raises(CommandError) as missing:
        call_command("catalog_export", output="/tmp/catalog.zip")
    assert "--organization" in str(missing.value)
    with pytest.raises(CommandError) as missing_output:
        call_command("catalog_export", organization=1)
    assert "--output" in str(missing_output.value)


@pytest.mark.django_db
def test_export_writes_package_without_overwriting_and_respects_feature_guard(tmp_path, capsys, settings):
    organization = Organization.objects.create(name="Command Export")
    output = tmp_path / "catalog.zip"
    settings.CATALOG_PORTABILITY_ENABLED = True
    call_command("catalog_export", organization=organization.pk, output=str(output))
    assert output.exists()
    assert json.loads(capsys.readouterr().out)["status"] == "successful"
    with pytest.raises(CommandError) as overwrite:
        call_command("catalog_export", organization=organization.pk, output=str(output))
    assert overwrite.value.returncode == 4
    settings.CATALOG_PORTABILITY_ENABLED = False
    with pytest.raises(CommandError) as disabled:
        call_command("catalog_export", organization=organization.pk, output=str(tmp_path / "other.zip"))
    assert disabled.value.returncode == 4


@pytest.mark.django_db
def test_validate_is_mutation_free_and_import_requires_confirmations(tmp_path, capsys, portability_enabled):
    organization = Organization.objects.create(name="Command Import")
    package = package_for([product_row("00000000-0000-4000-8000-000000000101", "COMMAND")])
    path = tmp_path / "input.zip"
    path.write_bytes(package)
    before = Product.objects.count()
    call_command("catalog_validate", organization=organization.pk, input=str(path), mode="merge")
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "valid"
    assert output["plan"]["organization_id"] == organization.pk
    assert Product.objects.count() == before
    package_sha = hashlib.sha256(package).hexdigest()
    with pytest.raises(CommandError) as missing_confirmation:
        call_command(
            "catalog_import",
            organization=organization.pk,
            input=str(path),
            mode="replace-storefront",
            operation_id=str(uuid.uuid4()),
            expected_catalog_digest=output["plan"]["target_digest"],
            confirm_package_sha256=package_sha,
        )
    assert missing_confirmation.value.returncode == 4


@pytest.mark.django_db
def test_invalid_validation_plan_has_nonzero_exit_and_bounded_result(tmp_path, capsys, portability_enabled):
    organization = Organization.objects.create(name="Command Invalid")
    first = Product.objects.create(
        organization=organization,
        name="FIRST",
        description="",
        product_type="physical",
        price="1.00",
        sku="FIRST",
        stock_quantity=0,
    )
    Product.objects.create(
        organization=organization,
        name="SECOND",
        description="",
        product_type="physical",
        price="2.00",
        sku="TAKEN",
        stock_quantity=0,
    )
    package = package_for([product_row(str(first.portable_id), "TAKEN")])
    path = tmp_path / "invalid.zip"
    path.write_bytes(package)
    with pytest.raises(CommandError) as error:
        call_command("catalog_validate", organization=organization.pk, input=str(path), mode="merge")
    output = json.loads(capsys.readouterr().out)
    assert error.value.returncode == 2
    assert output["status"] == "invalid"
    assert output["plan"]["actions_truncated"] is False
    assert output["plan"]["total_action_count"] == 0


@pytest.mark.django_db
def test_import_delegates_and_exact_retry_returns_same_receipt(tmp_path, capsys, portability_enabled):
    organization = Organization.objects.create(name="Command Apply")
    package = package_for([product_row("00000000-0000-4000-8000-000000000102", "APPLY")])
    path = tmp_path / "input.zip"
    path.write_bytes(package)
    call_command("catalog_validate", organization=organization.pk, input=str(path), mode="merge")
    plan = json.loads(capsys.readouterr().out)["plan"]
    operation_id = uuid.uuid4()
    arguments = {
        "organization": organization.pk,
        "input": str(path),
        "mode": "merge",
        "operation_id": str(operation_id),
        "expected_catalog_digest": plan["target_digest"],
        "confirm_package_sha256": hashlib.sha256(package).hexdigest(),
    }
    with override_settings(
        MEDIA_STORAGE_BACKEND="local",
        MEDIA_LOCAL_ROOT=str(tmp_path / "media"),
        MEDIA_PUBLIC_BASE_URL="http://localhost:8000/media",
        IS_PRODUCTION=False,
    ):
        get_media_storage.cache_clear()
        call_command("catalog_import", **arguments)
        first = json.loads(capsys.readouterr().out)["receipt"]
        call_command("catalog_import", **arguments)
        second = json.loads(capsys.readouterr().out)["receipt"]
        get_media_storage.cache_clear()
    assert first["operation_id"] == second["operation_id"]
    assert Product.objects.filter(organization=organization).count() == 1
    assert CatalogOperationReceipt.objects.count() == 1


@pytest.mark.django_db
def test_reset_validate_only_and_apply_require_no_http_route(tmp_path, capsys, portability_enabled, client):
    organization = Organization.objects.create(name="Command Reset")
    product = Product.objects.create(
        organization=organization,
        name="RESET",
        description="",
        product_type="physical",
        price="1.00",
        sku="RESET",
        stock_quantity=3,
    )
    call_command("catalog_reset_storefront", organization=organization.pk, validate_only=True)
    preview = json.loads(capsys.readouterr().out)["preview"]
    product.refresh_from_db()
    assert product.is_active is True
    operation_id = uuid.uuid4()
    call_command(
        "catalog_reset_storefront",
        organization=organization.pk,
        operation_id=str(operation_id),
        expected_catalog_digest=preview["target_digest"],
        confirm_organization=organization.pk,
    )
    assert json.loads(capsys.readouterr().out)["status"] == "successful"
    product.refresh_from_db()
    assert product.is_active is False
    assert client.post("/api/catalog/import/").status_code == 404
    assert client.post("/api/catalog/reset-storefront/").status_code == 404


@pytest.mark.django_db
def test_operation_status_found_and_not_recorded_are_non_failure_results(capsys, portability_enabled):
    organization = Organization.objects.create(name="Command Status")
    missing = uuid.uuid4()
    call_command("catalog_operation_status", organization=organization.pk, operation_id=str(missing))
    assert json.loads(capsys.readouterr().out)["status"] == "not_recorded"
    from catalog.portability.receipts import create_operation_receipt, operation_input_fingerprint

    receipt = create_operation_receipt(
        operation_id=uuid.uuid4(),
        organization_id=organization.pk,
        operation_type="catalog-reset-storefront",
        input_fingerprint=operation_input_fingerprint(
            organization_id=organization.pk,
            operation_type="catalog-reset-storefront",
            expected_catalog_digest="a" * 64,
            confirmation=str(organization.pk),
        ),
        result_counts={"deactivations": 0},
    )
    call_command("catalog_operation_status", organization=organization.pk, operation_id=str(receipt.operation_id))
    assert json.loads(capsys.readouterr().out)["receipt"]["status"] == "successful"
    organization.status = Organization.STATUS_INACTIVE
    organization.save(update_fields={"status", "updated_at"})
    call_command("catalog_operation_status", organization=organization.pk, operation_id=str(receipt.operation_id))
    assert json.loads(capsys.readouterr().out)["receipt"]["status"] == "successful"


@pytest.mark.django_db
def test_restore_snapshot_is_rejected_in_production_and_debug_does_not_bypass(
    tmp_path, portability_enabled, settings
):
    organization = Organization.objects.create(name="Production Policy")
    path = tmp_path / "input.zip"
    path.write_bytes(package_for())
    settings.COMMERCE_ENV = "production"
    settings.DEBUG = True
    with pytest.raises(CommandError) as error:
        call_command(
            "catalog_validate",
            organization=organization.pk,
            input=str(path),
            mode="merge",
            inventory="restore-snapshot",
        )
    assert error.value.returncode == 4
