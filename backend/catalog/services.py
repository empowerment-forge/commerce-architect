"""Shared Organization scope and PostgreSQL catalog mutation protocol."""

from __future__ import annotations

from contextlib import contextmanager

from django.conf import settings
from django.db import DatabaseError, connection, transaction

from catalog.models import Product, ProductImage
from organizations.models import Organization


LOCK_TIMEOUT_SECONDS = 5


class CatalogScopeError(ValueError):
    """The caller did not provide a valid explicit catalog scope."""


class CatalogBusyError(RuntimeError):
    code = "CATALOG_BUSY"


class CatalogNotConfigured(CatalogScopeError):
    """No valid explicit storefront Organization is configured."""


def _organization_id(value):
    organization_id = getattr(value, "pk", value)
    if isinstance(organization_id, bool) or not isinstance(organization_id, int):
        raise CatalogScopeError("an explicit Organization ID is required")
    if organization_id <= 0:
        raise CatalogScopeError("an explicit Organization ID is required")
    return organization_id


def get_active_organization(organization_id):
    organization_id = _organization_id(organization_id)
    try:
        return Organization.objects.get(
            pk=organization_id,
            status=Organization.STATUS_ACTIVE,
        )
    except Organization.DoesNotExist as exc:
        raise CatalogScopeError(
            f"active Organization does not exist: {organization_id}"
        ) from exc


def get_storefront_organization():
    configured_id = getattr(settings, "STOREFRONT_ORGANIZATION_ID", None)
    if configured_id is None:
        raise CatalogNotConfigured()
    try:
        return get_active_organization(configured_id)
    except CatalogScopeError as exc:
        raise CatalogNotConfigured() from exc


def scoped_products(organization_id, *, active_only=False, physical_only=False):
    organization_id = _organization_id(organization_id)
    queryset = Product.objects.filter(organization_id=organization_id)
    if active_only:
        queryset = queryset.filter(is_active=True)
    if physical_only:
        queryset = queryset.filter(product_type="physical")
    return queryset.order_by("portable_id")


def scoped_product_images(organization_id):
    organization_id = _organization_id(organization_id)
    return ProductImage.objects.filter(product__organization_id=organization_id).order_by(
        "product__portable_id", "sort_order", "portable_id"
    )


@contextmanager
def catalog_write_lock(organization_id):
    """Lock one Organization for the complete catalog mutation transaction."""

    organization_id = _organization_id(organization_id)
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT_SECONDS}s'")
            try:
                organization = Organization.objects.select_for_update().get(
                    pk=organization_id
                )
            except Organization.DoesNotExist as exc:
                raise CatalogScopeError(
                    f"Organization does not exist: {organization_id}"
                ) from exc
            yield organization
    except DatabaseError as exc:
        if getattr(exc, "__cause__", None) is not None and getattr(
            exc.__cause__, "pgcode", None
        ) == "55P03":
            raise CatalogBusyError(
                f"catalog Organization {organization_id} is busy"
            ) from exc
        raise
