"""Atomic, non-destructive storefront reset for one Organization."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from types import SimpleNamespace

from django.db import IntegrityError
from django.utils import timezone

from catalog.models import Product
from catalog.portability.compatibility import require_compatible_catalog
from catalog.portability.errors import CatalogPackageError
from catalog.portability.planner import (
    _capture_target_rows,
    _capture_target_rows_locked,
    _target_snapshot,
    _target_snapshot_from_rows,
    _target_state_token,
)
from catalog.portability.receipts import (
    create_operation_receipt,
    find_operation_receipt,
    operation_input_fingerprint,
)
from catalog.portability.schema import ErrorCode, SHA256_PATTERN
from catalog.services import CatalogBusyError, catalog_write_lock, get_active_organization
from organizations.models import Organization


OPERATION_TYPE = "catalog-reset-storefront"


@dataclass(frozen=True)
class StorefrontResetPreview:
    organization_id: int
    target_digest: str
    total_products: int
    active_products: int
    deactivations: int

    @property
    def valid(self) -> bool:
        return True

    def as_dict(self) -> dict[str, object]:
        return {
            "organization_id": self.organization_id,
            "target_digest": self.target_digest,
            "total_products": self.total_products,
            "active_products": self.active_products,
            "deactivations": self.deactivations,
        }


def _fail(message: str) -> None:
    raise CatalogPackageError(ErrorCode.OPERATION_NOT_ALLOWED, message)


def _validate_inputs(
    organization_id: int,
    operation_id: uuid.UUID,
    expected_catalog_digest: str,
    confirmed_organization_id: int | None,
) -> None:
    if isinstance(organization_id, bool) or not isinstance(organization_id, int) or organization_id <= 0:
        _fail("a positive Organization ID is required")
    if not isinstance(operation_id, uuid.UUID) or operation_id.version != 4:
        _fail("operation_id must be a UUIDv4")
    if not isinstance(expected_catalog_digest, str) or not SHA256_PATTERN.fullmatch(expected_catalog_digest):
        _fail("expected_catalog_digest must be a canonical lowercase SHA-256")
    if (
        isinstance(confirmed_organization_id, bool)
        or not isinstance(confirmed_organization_id, int)
        or confirmed_organization_id <= 0
    ):
        _fail("storefront reset requires Organization confirmation")
    if confirmed_organization_id != organization_id:
        _fail("Organization confirmation does not match the selected Organization")


def _fingerprint(organization_id: int, expected_catalog_digest: str, confirmation: int) -> str:
    return operation_input_fingerprint(
        organization_id=organization_id,
        operation_type=OPERATION_TYPE,
        expected_catalog_digest=expected_catalog_digest,
        confirmation=str(confirmation),
    )


def _prepared_media(snapshot) -> dict[str, object]:
    """The reset never changes media; preserve verified media for digest reuse."""
    images = {
        (image["product_portable_id"], image["portable_id"]): image
        for image in snapshot.images
    }
    return {
        storage_key: SimpleNamespace(
            asset_path=images[(product_id, image_id)]["asset_path"],
            sha256=images[(product_id, image_id)]["content_sha256"],
        )
        for product_id, image_id, storage_key in snapshot.image_storage_keys
    }


def preview_storefront_reset(organization_id: int, *, storage_adapter=None) -> StorefrontResetPreview:
    """Build a mutation-free reset preview for one active Organization."""

    organization = get_active_organization(organization_id)
    require_compatible_catalog()
    snapshot = _target_snapshot(organization.pk, storage_adapter)
    active_products = Product.objects.filter(
        organization_id=organization.pk,
        is_active=True,
    ).count()
    return StorefrontResetPreview(
        organization_id=organization.pk,
        target_digest=snapshot.digest,
        total_products=len(snapshot.products),
        active_products=active_products,
        deactivations=active_products,
    )


plan_storefront_reset = preview_storefront_reset


def apply_storefront_reset(
    organization_id: int,
    *,
    operation_id: uuid.UUID,
    expected_catalog_digest: str,
    confirmed_organization_id: int | None = None,
    storage_adapter=None,
):
    """Atomically deactivate active Products without deleting catalog data."""

    _validate_inputs(
        organization_id,
        operation_id,
        expected_catalog_digest,
        confirmed_organization_id,
    )
    fingerprint = _fingerprint(
        organization_id,
        expected_catalog_digest,
        confirmed_organization_id,
    )
    existing = find_operation_receipt(operation_id, input_fingerprint=fingerprint)
    if existing is not None:
        return existing

    organization = get_active_organization(organization_id)
    require_compatible_catalog()
    preflight = _target_snapshot(organization.pk, storage_adapter)
    if preflight.digest != expected_catalog_digest:
        raise CatalogPackageError(
            ErrorCode.STALE_TARGET,
            "target catalog changed since reset preview",
        )
    preflight_rows = _capture_target_rows(organization.pk)
    preflight_token = _target_state_token(preflight_rows[0], preflight_rows[1])
    prepared_media = _prepared_media(preflight)

    try:
        with catalog_write_lock(organization.pk) as locked_organization:
            if locked_organization.status != Organization.STATUS_ACTIVE:
                _fail("reset requires an active Organization")
            locked_receipt = find_operation_receipt(
                operation_id,
                input_fingerprint=fingerprint,
            )
            if locked_receipt is not None:
                return locked_receipt
            locked_rows = _capture_target_rows_locked(organization.pk)
            if _target_state_token(locked_rows[0], locked_rows[1]) != preflight_token:
                raise CatalogPackageError(
                    ErrorCode.STALE_TARGET,
                    "target catalog changed during reset preparation",
                )
            locked_target = _target_snapshot_from_rows(*locked_rows, prepared_media)
            if locked_target.digest != expected_catalog_digest:
                raise CatalogPackageError(
                    ErrorCode.STALE_TARGET,
                    "target catalog digest changed during reset preparation",
                )

            active = Product.objects.filter(
                organization_id=organization.pk,
                is_active=True,
            )
            deactivation_count = active.count()
            if deactivation_count:
                active.update(is_active=False, updated_at=timezone.now())

            final_rows = _capture_target_rows_locked(organization.pk)
            final_target = _target_snapshot_from_rows(*final_rows, prepared_media)
            return_value = create_operation_receipt(
                operation_id=operation_id,
                organization_id=organization.pk,
                operation_type=OPERATION_TYPE,
                input_fingerprint=fingerprint,
                expected_catalog_digest=expected_catalog_digest,
                pre_catalog_digest=expected_catalog_digest,
                post_catalog_digest=final_target.digest,
                result_counts={"deactivations": deactivation_count},
            )
        return return_value
    except IntegrityError:
        winner = find_operation_receipt(operation_id, input_fingerprint=fingerprint)
        if winner is not None:
            return winner
        _fail("storefront reset transaction failed")
    except (CatalogPackageError, CatalogBusyError):
        raise
    except Exception as exc:
        try:
            resolved = find_operation_receipt(
                operation_id,
                input_fingerprint=fingerprint,
            )
        except Exception as resolution_exc:
            raise CatalogPackageError(
                ErrorCode.OUTCOME_UNKNOWN,
                "storefront reset outcome could not be established",
            ) from resolution_exc
        if resolved is not None:
            return resolved
        raise CatalogPackageError(
            ErrorCode.IMPORT_FAILED,
            "storefront reset transaction failed",
        ) from exc


reset_storefront = apply_storefront_reset
