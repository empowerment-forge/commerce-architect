"""Reviewed, one-time Product foundation bootstrap."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from catalog.models import Product
from catalog.portability.schema import MAX_STOCK_QUANTITY, SKU_PATTERN
from catalog.services import catalog_write_lock
from organizations.models import Organization


class BootstrapValidationError(ValueError):
    """A mapping is not a complete, reviewed Product bootstrap map."""

    def __init__(self, errors):
        self.errors = tuple(errors)
        super().__init__("; ".join(self.errors))


@dataclass(frozen=True)
class BootstrapPlan:
    organization_id: int
    fingerprint: str
    assignments: tuple[tuple[int, str, int], ...]


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate mapping key: {key}")
        result[key] = value
    return result


def load_mapping(path: str | Path) -> dict:
    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            value = json.load(handle, object_pairs_hook=_reject_duplicate_keys)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise BootstrapValidationError((f"invalid mapping JSON: {exc}",)) from exc
    if not isinstance(value, dict):
        raise BootstrapValidationError(("mapping must be a JSON object",))
    return value


def mapping_fingerprint(mapping: dict) -> str:
    canonical = json.dumps(
        mapping,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _mapping_rows(mapping):
    errors = []
    if set(mapping) != {"organization_id", "products"}:
        errors.append("mapping must contain exactly organization_id and products")
    organization_id = mapping.get("organization_id")
    if isinstance(organization_id, bool) or not isinstance(organization_id, int):
        errors.append("organization_id must be an integer")
    elif organization_id <= 0:
        errors.append("organization_id must be positive")

    rows = mapping.get("products")
    if not isinstance(rows, list):
        errors.append("products must be an array")
        rows = []

    normalized = []
    seen_pks = set()
    seen_skus = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != {
            "product_pk",
            "sku",
            "stock_quantity",
        }:
            errors.append(f"products[{index}] must contain exactly product_pk, sku, stock_quantity")
            continue
        product_pk = row["product_pk"]
        sku = row["sku"]
        stock = row["stock_quantity"]
        if isinstance(product_pk, bool) or not isinstance(product_pk, int) or product_pk <= 0:
            errors.append(f"products[{index}].product_pk must be a positive integer")
        elif product_pk in seen_pks:
            errors.append(f"duplicate product_pk: {product_pk}")
        else:
            seen_pks.add(product_pk)
        if not isinstance(sku, str) or not re.fullmatch(SKU_PATTERN, sku):
            errors.append(f"products[{index}].sku is not canonical")
        elif sku in seen_skus:
            errors.append(f"duplicate SKU: {sku}")
        else:
            seen_skus.add(sku)
        if (
            isinstance(stock, bool)
            or not isinstance(stock, int)
            or not 0 <= stock <= MAX_STOCK_QUANTITY
        ):
            errors.append(f"products[{index}].stock_quantity is out of range")
        if isinstance(product_pk, int) and product_pk > 0 and isinstance(sku, str) and isinstance(stock, int) and not isinstance(stock, bool):
            normalized.append((product_pk, sku, stock))
    return organization_id, normalized, errors


def validate_mapping(mapping: dict, organization_id: int, products=None) -> BootstrapPlan:
    selected = Organization.objects.filter(pk=organization_id).first()
    errors = []
    if selected is None:
        errors.append(f"unknown Organization: {organization_id}")
    elif selected.status != Organization.STATUS_ACTIVE:
        errors.append(f"Organization is not active: {organization_id}")

    mapped_organization_id, assignments, mapping_errors = _mapping_rows(mapping)
    errors.extend(mapping_errors)
    if mapped_organization_id != organization_id:
        errors.append("mapping organization_id does not match selected Organization")

    current_products = list(Product.objects.all() if products is None else products)
    current_by_pk = {product.pk: product for product in current_products}
    mapped_pks = {product_pk for product_pk, _, _ in assignments}
    unknown_pks = sorted(mapped_pks - set(current_by_pk))
    missing_pks = sorted(set(current_by_pk) - mapped_pks)
    if unknown_pks:
        errors.append(f"unknown Product PKs: {unknown_pks}")
    if missing_pks:
        errors.append(f"missing Product PKs: {missing_pks}")

    existing_skus = {
        product.sku
        for product in current_products
        if (
            product.pk not in mapped_pks
            and product.organization_id == organization_id
            and product.sku
        )
    }
    mapped_skus = {sku for _, sku, _ in assignments}
    if existing_skus & mapped_skus:
        conflicts = sorted(existing_skus & mapped_skus)
        errors.append(f"SKU conflict: {conflicts}")

    for product_pk, _, _ in assignments:
        product = current_by_pk.get(product_pk)
        if product is not None and product.product_type != "physical":
            errors.append(f"unsupported service Product PK: {product_pk}")

    if errors:
        raise BootstrapValidationError(tuple(errors))
    return BootstrapPlan(
        organization_id=organization_id,
        fingerprint=mapping_fingerprint(mapping),
        assignments=tuple(assignments),
    )


def apply_mapping(mapping: dict, organization_id: int, expected_fingerprint: str):
    fingerprint = mapping_fingerprint(mapping)
    if expected_fingerprint != fingerprint:
        raise BootstrapValidationError(("mapping fingerprint does not match reviewed fingerprint",))
    with catalog_write_lock(organization_id):
        locked_products = list(Product.objects.select_for_update().all())
        plan = validate_mapping(mapping, organization_id, products=locked_products)
        for product_pk, sku, stock_quantity in plan.assignments:
            Product.objects.filter(pk=product_pk).update(
                organization_id=organization_id,
                sku=sku,
                stock_quantity=stock_quantity,
            )
    return plan
