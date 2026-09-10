"""Durable idempotency receipts for trusted catalog operator services."""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from django.db import IntegrityError

from catalog.models import CatalogOperationReceipt
from catalog.portability.codec import canonical_json_bytes
from catalog.portability.errors import CatalogPackageError
from catalog.portability.schema import ErrorCode


def operation_input_fingerprint(
    *,
    organization_id: int,
    operation_type: str,
    mode: str | None = None,
    package_sha256: str | None = None,
    inventory_policy: str | None = None,
    expected_catalog_digest: str | None = None,
    confirmation: str | None = None,
) -> str:
    """Hash the complete semantic input set, including operator confirmation."""

    value = {
        "organization_id": organization_id,
        "operation_type": operation_type,
        "mode": mode,
        "package_sha256": package_sha256,
        "inventory_policy": inventory_policy,
        "expected_catalog_digest": expected_catalog_digest,
        "confirmation": confirmation,
    }
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _conflict(operation_id: uuid.UUID) -> CatalogPackageError:
    return CatalogPackageError(
        ErrorCode.OPERATION_ID_CONFLICT,
        f"operation_id {operation_id} was already used with different semantic inputs",
    )


def find_operation_receipt(
    operation_id: uuid.UUID,
    *,
    input_fingerprint: str,
) -> CatalogOperationReceipt | None:
    """Return an exact prior receipt, or fail closed on semantic reuse."""

    receipt = CatalogOperationReceipt.objects.filter(operation_id=operation_id).first()
    if receipt is None:
        return None
    if receipt.input_fingerprint != input_fingerprint:
        raise _conflict(operation_id)
    return receipt


def create_operation_receipt(
    *,
    operation_id: uuid.UUID,
    organization_id: int,
    operation_type: str,
    input_fingerprint: str,
    package_sha256: str | None = None,
    inventory_policy: str | None = None,
    expected_catalog_digest: str | None = None,
    pre_catalog_digest: str | None = None,
    post_catalog_digest: str | None = None,
    result_counts: dict[str, Any] | None = None,
) -> CatalogOperationReceipt:
    """Persist a successful receipt inside the caller's transaction."""

    try:
        return CatalogOperationReceipt.objects.create(
            operation_id=operation_id,
            organization_id=organization_id,
            operation_type=operation_type,
            input_fingerprint=input_fingerprint,
            package_sha256=package_sha256,
            inventory_policy=inventory_policy,
            expected_catalog_digest=expected_catalog_digest,
            pre_catalog_digest=pre_catalog_digest,
            post_catalog_digest=post_catalog_digest,
            result_counts=result_counts or {},
        )
    except IntegrityError:
        existing = CatalogOperationReceipt.objects.filter(operation_id=operation_id).first()
        if existing is not None and existing.input_fingerprint == input_fingerprint:
            return existing
        raise _conflict(operation_id)


def get_or_create_operation_receipt(
    *,
    operation_id: uuid.UUID,
    input_fingerprint: str,
    **receipt_fields: Any,
) -> tuple[CatalogOperationReceipt, bool]:
    """Resolve an exact retry or create the receipt for a successful operation."""

    existing = find_operation_receipt(
        operation_id,
        input_fingerprint=input_fingerprint,
    )
    if existing is not None:
        return existing, False
    return (
        create_operation_receipt(
            operation_id=operation_id,
            input_fingerprint=input_fingerprint,
            **receipt_fields,
        ),
        True,
    )
