import uuid

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from catalog.models import CatalogOperationReceipt, Product
from catalog.portability.errors import CatalogPackageError
from catalog.portability.receipts import (
    create_operation_receipt,
    find_operation_receipt,
    get_or_create_operation_receipt,
    operation_input_fingerprint,
)
from organizations.models import Organization


def receipt_inputs(organization, *, mode="merge", package="a" * 64):
    return operation_input_fingerprint(
        organization_id=organization.pk,
        operation_type="catalog_import",
        mode=mode,
        package_sha256=package,
        inventory_policy="preserve",
        expected_catalog_digest="b" * 64,
        confirmation="The Empowerment Forge",
    )


def create_receipt(organization, operation_id, fingerprint):
    return create_operation_receipt(
        operation_id=operation_id,
        organization_id=organization.pk,
        operation_type="catalog_import",
        input_fingerprint=fingerprint,
        package_sha256="a" * 64,
        inventory_policy="preserve",
        expected_catalog_digest="b" * 64,
        pre_catalog_digest="c" * 64,
        post_catalog_digest="d" * 64,
        result_counts={"creates": 1},
    )


@pytest.mark.django_db
def test_exact_retry_returns_prior_receipt_without_replaying_mutation():
    organization = Organization.objects.create(name="Receipts")
    operation_id = uuid.uuid4()
    fingerprint = receipt_inputs(organization)
    first, created = get_or_create_operation_receipt(
        operation_id=operation_id,
        input_fingerprint=fingerprint,
        organization_id=organization.pk,
        operation_type="catalog_import",
        result_counts={"creates": 1},
    )
    second, retried = get_or_create_operation_receipt(
        operation_id=operation_id,
        input_fingerprint=fingerprint,
        organization_id=organization.pk,
        operation_type="catalog_import",
        result_counts={"creates": 999},
    )

    assert created is True
    assert retried is False
    assert second.pk == first.pk
    assert second.result_counts == {"creates": 1}


@pytest.mark.django_db
@pytest.mark.parametrize("changed", ["mode", "package", "target", "policy", "confirmation"])
def test_changed_semantic_input_is_rejected(changed):
    organization = Organization.objects.create(name=f"Conflict {changed}")
    operation_id = uuid.uuid4()
    fingerprint = receipt_inputs(organization)
    create_receipt(organization, operation_id, fingerprint)
    kwargs = {
        "mode": "merge",
        "package": "a" * 64,
        "target": "b" * 64,
        "policy": "preserve",
        "confirmation": "The Empowerment Forge",
    }
    kwargs[changed] = {
        "mode": "replace-storefront",
        "package": "e" * 64,
        "target": "f" * 64,
        "policy": "restore-snapshot",
        "confirmation": "different",
    }[changed]
    changed_fingerprint = operation_input_fingerprint(
        organization_id=organization.pk,
        operation_type="catalog_import",
        mode=kwargs["mode"],
        package_sha256=kwargs["package"],
        inventory_policy=kwargs["policy"],
        expected_catalog_digest=kwargs["target"],
        confirmation=kwargs["confirmation"],
    )

    with pytest.raises(CatalogPackageError) as exc:
        find_operation_receipt(operation_id, input_fingerprint=changed_fingerprint)
    assert exc.value.code.value == "OPERATION_ID_CONFLICT"


@pytest.mark.django_db
def test_concurrent_operation_id_is_unique():
    organization = Organization.objects.create(name="Unique")
    operation_id = uuid.uuid4()
    fingerprint = receipt_inputs(organization)
    create_receipt(organization, operation_id, fingerprint)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CatalogOperationReceipt.objects.create(
                operation_id=operation_id,
                organization=organization,
                operation_type="catalog_import",
                input_fingerprint=fingerprint,
            )


@pytest.mark.django_db
def test_rollback_does_not_leave_receipt_and_receipt_survives_catalog_purge():
    organization = Organization.objects.create(name="Durable")
    operation_id = uuid.uuid4()
    fingerprint = receipt_inputs(organization)
    with pytest.raises(RuntimeError):
        with transaction.atomic():
            create_receipt(organization, operation_id, fingerprint)
            raise RuntimeError("simulated failure")
    assert not CatalogOperationReceipt.objects.filter(operation_id=operation_id).exists()

    receipt = create_receipt(organization, operation_id, fingerprint)
    Product.objects.create(
        organization=organization,
        name="Temporary",
        description="",
        product_type="physical",
        price="1.00",
        sku="TEMPORARY",
        stock_quantity=0,
    )
    Product.objects.all().delete()
    assert CatalogOperationReceipt.objects.get(pk=receipt.pk).pk == receipt.pk


@pytest.mark.django_db
def test_completion_time_and_receipt_are_immutable():
    organization = Organization.objects.create(name="Immutable")
    receipt = create_receipt(organization, uuid.uuid4(), receipt_inputs(organization))
    completed_at = receipt.completed_at
    receipt.result_counts = {"creates": 2}
    with pytest.raises(ValidationError):
        receipt.save()
    assert CatalogOperationReceipt.objects.get(pk=receipt.pk).completed_at == completed_at
