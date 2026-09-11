"""Explicit portability compatibility declarations for the installed catalog."""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

from catalog.models import Product, ProductImage
from catalog.portability.errors import CatalogPackageError
from catalog.portability.schema import ErrorCode


SUPPORTED_PRODUCT_FIELDS = frozenset(
    {
        "id",
        "name",
        "description",
        "product_type",
        "price",
        "is_active",
        "created_at",
        "organization",
        "sku",
        "stock_quantity",
        "portable_id",
        "updated_at",
    }
)
SUPPORTED_PRODUCT_IMAGE_FIELDS = frozenset(
    {
        "id",
        "product",
        "portable_id",
        "storage_key",
        "alt_text",
        "sort_order",
        "is_primary",
        "created_at",
        "updated_at",
    }
)
SUPPORTED_PRODUCT_RELATIONS = frozenset({"images"})
SUPPORTED_PRODUCT_IMAGE_RELATIONS = frozenset()
DECLARED_INVENTORY_PROTECTIONS = frozenset()


@dataclass(frozen=True)
class PurgeRelationSpec:
    """A relation reviewed specifically for the development purge boundary."""

    source_label: str
    field_name: str
    target_label: str
    kind: str = "foreign_key"
    through_label: str | None = None
    through_field_name: str | None = None


@dataclass(frozen=True)
class PurgeGenericReferenceSpec:
    model_label: str
    content_type_field: str
    object_id_field: str


# This registry is intentionally separate from the normal portability allowlist.
PURGE_INTERNAL_DELETE_EDGES = (
    PurgeRelationSpec("catalog.ProductImage", "product", "catalog.Product"),
)
PURGE_EXTERNAL_RELATION_SPECS: tuple[PurgeRelationSpec, ...] = ()
PURGE_GENERIC_REFERENCE_SPECS = (
    PurgeGenericReferenceSpec("admin.LogEntry", "content_type", "object_id"),
)
PURGE_CUSTOM_INSPECTORS: dict[str, object] = {}


@dataclass(frozen=True)
class CompatibilityIssue:
    code: ErrorCode
    identity: str
    message: str


def _field_names(model) -> set[str]:
    return {field.name for field in model._meta.concrete_fields}


def _relation_names(model) -> set[str]:
    return {relation.get_accessor_name() for relation in model._meta.related_objects}


def compatibility_issues() -> tuple[CompatibilityIssue, ...]:
    issues: list[CompatibilityIssue] = []
    product_fields = _field_names(Product)
    unknown_product_fields = sorted(product_fields - SUPPORTED_PRODUCT_FIELDS)
    missing_product_fields = sorted(SUPPORTED_PRODUCT_FIELDS - product_fields)
    for field in unknown_product_fields:
        issues.append(
            CompatibilityIssue(
                ErrorCode.UNSUPPORTED_SCHEMA,
                f"Product.{field}",
                "Product concrete field has no portability disposition",
            )
        )
    for field in missing_product_fields:
        issues.append(
            CompatibilityIssue(
                ErrorCode.UNSUPPORTED_SCHEMA,
                f"Product.{field}",
                "declared portable Product field is not installed",
            )
        )

    product_image_fields = _field_names(ProductImage)
    for field in sorted(product_image_fields - SUPPORTED_PRODUCT_IMAGE_FIELDS):
        issues.append(
            CompatibilityIssue(
                ErrorCode.UNSUPPORTED_SCHEMA,
                f"ProductImage.{field}",
                "ProductImage concrete field has no portability disposition",
            )
        )
    for field in sorted(SUPPORTED_PRODUCT_IMAGE_FIELDS - product_image_fields):
        issues.append(
            CompatibilityIssue(
                ErrorCode.UNSUPPORTED_SCHEMA,
                f"ProductImage.{field}",
                "declared portable ProductImage field is not installed",
            )
        )

    for relation in sorted(_relation_names(Product) - SUPPORTED_PRODUCT_RELATIONS):
        issues.append(
            CompatibilityIssue(
                ErrorCode.UNSUPPORTED_SCHEMA,
                f"Product.{relation}",
                "Product relation has no portability disposition",
            )
        )
    for relation in sorted(_relation_names(ProductImage) - SUPPORTED_PRODUCT_IMAGE_RELATIONS):
        issues.append(
            CompatibilityIssue(
                ErrorCode.UNSUPPORTED_SCHEMA,
                f"ProductImage.{relation}",
                "ProductImage relation has no portability disposition",
            )
        )

    configured_integrations = getattr(
        settings,
        "CATALOG_INVENTORY_PROTECTION_INTEGRATIONS",
        (),
    )
    if configured_integrations:
        issues.append(
            CompatibilityIssue(
                ErrorCode.UNSUPPORTED_SCHEMA,
                "inventory",
                "inventory protection integration is not declared for portability",
            )
        )
    return tuple(sorted(issues, key=lambda issue: (issue.identity, issue.code.value)))


def require_compatible_catalog() -> None:
    issues = compatibility_issues()
    if issues:
        issue = issues[0]
        raise CatalogPackageError(issue.code, issue.message, path=issue.identity)


def inventory_protections_active() -> bool:
    """Return whether a reviewed inventory protection is active.

    T04–T10 declare no inventory integrations. An unknown configured integration
    is rejected by ``require_compatible_catalog`` rather than treated as none.
    """

    require_compatible_catalog()
    return bool(DECLARED_INVENTORY_PROTECTIONS)
