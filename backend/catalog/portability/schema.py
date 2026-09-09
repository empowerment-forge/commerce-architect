"""The versioned, ORM-independent Catalog Portability v1 schema.

This module deliberately contains no Django model or transport introspection.
Later packets may use these contracts, but validation here has no side effects.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, Mapping


FORMAT = "commerce-architect-catalog"
FORMAT_VERSION = 1
DOMAIN_SCHEMA = "product-commerce-catalog/1"
ENTITY_VERSIONS = {"product": 1, "product_image": 1}
REQUIRED_FEATURES = (
    "embedded-images",
    "organization-scope",
    "portable-identities",
    "stock-snapshot",
)
SCOPE = {"kind": "organization", "coverage": "full"}
CURRENCY = "USD"
INVENTORY_SEMANTICS = "snapshot-not-reservation"

PRODUCT_FIELDS = (
    "portable_id",
    "sku",
    "name",
    "description",
    "price",
    "stock_quantity",
    "status",
)
PRODUCT_IMAGE_FIELDS = (
    "portable_id",
    "product_portable_id",
    "asset_path",
    "alt_text",
    "sort_order",
    "is_primary",
)
MANIFEST_FIELDS = (
    "format",
    "format_version",
    "domain_schema",
    "entity_versions",
    "required_features",
    "scope",
    "currency",
    "inventory_semantics",
    "counts",
    "files",
)
FILE_DESCRIPTOR_FIELDS = ("path", "sha256", "size_bytes", "media_type")

SKU_PATTERN = re.compile(r"[A-Z0-9][A-Z0-9._-]{0,63}\Z")
UUID4_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z"
)
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
MEDIA_TYPES = ("image/jpeg", "image/png", "image/webp")
CATALOG_MEDIA_TYPE = "application/json"
PRODUCT_STATUSES = ("active", "inactive")
ZIP_FILE_LIMIT_BYTES = 520 * 1024 * 1024
TOTAL_UNCOMPRESSED_MEMBER_LIMIT_BYTES = 512 * 1024 * 1024
MANIFEST_LIMIT_BYTES = 8 * 1024 * 1024
CATALOG_LIMIT_BYTES = 16 * 1024 * 1024
MAX_PRODUCTS = 10_000
MAX_PRODUCT_IMAGES = 20_000
MAX_IMAGES_PER_PRODUCT = 50
MAX_REGULAR_FILE_ENTRIES = 20_002
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
MAX_IMAGE_DIMENSION = 12_000
MAX_JSON_NESTING = 16
MAX_DESCRIPTION_UTF8_BYTES = 1024 * 1024
MAX_NAME_CHARS = 255
MAX_ALT_TEXT_CHARS = 2_000
MAX_STOCK_QUANTITY = 2_147_483_647
MAX_SORT_ORDER = 2_147_483_647
MIN_PRICE = Decimal("0.00")
MAX_PRICE = Decimal("99999999.99")


class ErrorCode(StrEnum):
    INVALID_PACKAGE = "INVALID_PACKAGE"
    UNSUPPORTED_SCHEMA = "UNSUPPORTED_SCHEMA"
    INVALID_IMAGE = "INVALID_IMAGE"
    DUPLICATE_ID = "DUPLICATE_ID"
    DUPLICATE_SKU = "DUPLICATE_SKU"
    SKU_CONFLICT = "SKU_CONFLICT"
    UNSAFE_ARCHIVE = "UNSAFE_ARCHIVE"
    LIMIT_EXCEEDED = "LIMIT_EXCEEDED"
    MEDIA_UNAVAILABLE = "MEDIA_UNAVAILABLE"
    STALE_TARGET = "STALE_TARGET"
    PACKAGE_CHANGED = "PACKAGE_CHANGED"
    CATALOG_BUSY = "CATALOG_BUSY"
    IMPORT_FAILED = "IMPORT_FAILED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"
    REFERENCED_CATALOG = "REFERENCED_CATALOG"
    OPERATION_NOT_ALLOWED = "OPERATION_NOT_ALLOWED"
    OPERATION_ID_CONFLICT = "OPERATION_ID_CONFLICT"


@dataclass(frozen=True)
class FieldContract:
    name: str
    representation: str
    required: bool = True
    nullable: bool = False


PRODUCT_FIELD_CONTRACTS = tuple(
    FieldContract(name, representation)
    for name, representation in (
        ("portable_id", "canonical lowercase hyphenated UUIDv4"),
        ("sku", "ASCII string matching [A-Z0-9][A-Z0-9._-]{0,63}"),
        ("name", "nonblank Unicode string of at most 255 characters"),
        ("description", "string of at most 1 MiB UTF-8 bytes"),
        ("price", "USD decimal string with exactly two fractional digits"),
        ("stock_quantity", "integer from 0 through 2,147,483,647"),
        ("status", "the active or inactive enum"),
    )
)
PRODUCT_IMAGE_FIELD_CONTRACTS = tuple(
    FieldContract(name, representation)
    for name, representation in (
        ("portable_id", "canonical lowercase hyphenated UUIDv4"),
        ("product_portable_id", "portable_id of a product in this package"),
        ("asset_path", "listed media/<lowercase-sha256>.<jpg|png|webp> path"),
        ("alt_text", "string of at most 2,000 Unicode characters"),
        ("sort_order", "integer from 0 through 2,147,483,647"),
        ("is_primary", "boolean"),
    )
)


class SchemaValidationError(ValueError):
    """A schema error with a stable v1 code and JSON-like field path."""

    def __init__(self, code: ErrorCode, path: str, message: str):
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{code} at {path}: {message}")


def _fail(path: str, message: str, code: ErrorCode = ErrorCode.INVALID_PACKAGE) -> None:
    raise SchemaValidationError(code, path, message)


def _object(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        _fail(path, "must be an object")
    return value


def _exact_keys(value: Mapping[str, Any], expected: tuple[str, ...], path: str) -> None:
    actual = set(value)
    missing = set(expected) - actual
    unknown = actual - set(expected)
    if missing or unknown:
        details = []
        if missing:
            details.append(f"missing {sorted(missing)}")
        if unknown:
            details.append(f"unknown {sorted(unknown)}")
        _fail(path, "; ".join(details))


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str):
        _fail(path, "must be a string")
    return value


def _integer(value: Any, path: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(path, "must be an integer (boolean is not an integer)")
    if not minimum <= value <= maximum:
        _fail(path, f"must be between {minimum} and {maximum}")
    return value


def _uuid4(value: Any, path: str) -> str:
    value = _string(value, path)
    if not UUID4_PATTERN.fullmatch(value):
        _fail(path, "must be a canonical lowercase UUIDv4")
    try:
        if str(uuid.UUID(value)) != value or uuid.UUID(value).version != 4:
            _fail(path, "must be a canonical lowercase UUIDv4")
    except ValueError:
        _fail(path, "must be a canonical lowercase UUIDv4")
    return value


def _validate_product(value: Any, index: int) -> str:
    path = f"products[{index}]"
    product = _object(value, path)
    _exact_keys(product, PRODUCT_FIELDS, path)
    portable_id = _uuid4(product["portable_id"], f"{path}.portable_id")
    sku = _string(product["sku"], f"{path}.sku")
    if not SKU_PATTERN.fullmatch(sku):
        _fail(f"{path}.sku", "must match the canonical ASCII SKU pattern")
    name = _string(product["name"], f"{path}.name")
    if not 1 <= len(name) <= MAX_NAME_CHARS or not any(not char.isspace() for char in name):
        _fail(f"{path}.name", "must contain non-whitespace and be at most 255 characters")
    description = _string(product["description"], f"{path}.description")
    if len(description.encode("utf-8")) > MAX_DESCRIPTION_UTF8_BYTES:
        _fail(f"{path}.description", "must be at most 1 MiB in UTF-8")
    price = _string(product["price"], f"{path}.price")
    if not re.fullmatch(r"(?:0|[1-9][0-9]{0,7})\.[0-9]{2}", price):
        _fail(f"{path}.price", "must be a canonical unsigned USD decimal")
    try:
        decimal_price = Decimal(price)
    except InvalidOperation:
        _fail(f"{path}.price", "must be a valid decimal")
    if not MIN_PRICE <= decimal_price <= MAX_PRICE:
        _fail(f"{path}.price", "is outside the v1 USD range")
    _integer(product["stock_quantity"], f"{path}.stock_quantity", minimum=0, maximum=MAX_STOCK_QUANTITY)
    if not isinstance(product["status"], str) or product["status"] not in PRODUCT_STATUSES:
        _fail(f"{path}.status", "must be active or inactive")
    return portable_id


def _asset_path(value: Any, path: str) -> str:
    value = _string(value, path)
    if not re.fullmatch(r"media/[0-9a-f]{64}\.(?:jpg|png|webp)", value):
        _fail(path, "must be an exact media SHA-256 path")
    return value


def _validate_product_image(value: Any, index: int, product_ids: set[str]) -> tuple[str, str]:
    path = f"product_images[{index}]"
    image = _object(value, path)
    _exact_keys(image, PRODUCT_IMAGE_FIELDS, path)
    image_id = _uuid4(image["portable_id"], f"{path}.portable_id")
    product_id = _uuid4(image["product_portable_id"], f"{path}.product_portable_id")
    if product_id not in product_ids:
        _fail(f"{path}.product_portable_id", "must reference a listed product")
    _asset_path(image["asset_path"], f"{path}.asset_path")
    alt_text = _string(image["alt_text"], f"{path}.alt_text")
    if len(alt_text) > MAX_ALT_TEXT_CHARS:
        _fail(f"{path}.alt_text", "must be at most 2,000 characters")
    _integer(image["sort_order"], f"{path}.sort_order", minimum=0, maximum=MAX_SORT_ORDER)
    if not isinstance(image["is_primary"], bool):
        _fail(f"{path}.is_primary", "must be a boolean")
    return image_id, product_id


def validate_catalog(value: Any) -> None:
    """Validate a decoded catalog.json document without mutating it."""
    catalog = _object(value, "catalog")
    _exact_keys(catalog, ("products", "product_images"), "catalog")
    if not isinstance(catalog["products"], list) or not isinstance(catalog["product_images"], list):
        _fail("catalog", "products and product_images must be arrays")
    if len(catalog["products"]) > MAX_PRODUCTS:
        _fail("catalog.products", "product limit exceeded", ErrorCode.LIMIT_EXCEEDED)
    if len(catalog["product_images"]) > MAX_PRODUCT_IMAGES:
        _fail("catalog.product_images", "image record limit exceeded", ErrorCode.LIMIT_EXCEEDED)
    product_ids = [_validate_product(product, index) for index, product in enumerate(catalog["products"])]
    if len(product_ids) != len(set(product_ids)):
        _fail("catalog.products", "duplicate product portable_id", ErrorCode.DUPLICATE_ID)
    image_ids_by_product: dict[str, set[str]] = {}
    image_count_by_product: dict[str, int] = {}
    primary_count_by_product: dict[str, int] = {}
    for index, image in enumerate(catalog["product_images"]):
        image_id, product_id = _validate_product_image(image, index, set(product_ids))
        ids = image_ids_by_product.setdefault(product_id, set())
        if image_id in ids:
            _fail(f"product_images[{index}].portable_id", "duplicate image portable_id for product", ErrorCode.DUPLICATE_ID)
        ids.add(image_id)
        image_count_by_product[product_id] = image_count_by_product.get(product_id, 0) + 1
        if image_count_by_product[product_id] > MAX_IMAGES_PER_PRODUCT:
            _fail(f"product_images[{index}]", "per-product image limit exceeded", ErrorCode.LIMIT_EXCEEDED)
        if image["is_primary"]:
            primary_count_by_product[product_id] = primary_count_by_product.get(product_id, 0) + 1
            if primary_count_by_product[product_id] > 1:
                _fail(f"product_images[{index}].is_primary", "a product may have at most one primary image")


def validate_manifest(value: Any) -> None:
    """Validate the exact manifest contract; archive membership is T07."""
    manifest = _object(value, "manifest")
    _exact_keys(manifest, MANIFEST_FIELDS, "manifest")
    if not isinstance(manifest["format"], str) or not isinstance(manifest["domain_schema"], str) or manifest["format"] != FORMAT or manifest["domain_schema"] != DOMAIN_SCHEMA:
        _fail("manifest", "unsupported format or domain schema", ErrorCode.UNSUPPORTED_SCHEMA)
    if isinstance(manifest["format_version"], bool) or not isinstance(manifest["format_version"], int) or manifest["format_version"] != FORMAT_VERSION:
        _fail("manifest.format_version", "unsupported format version", ErrorCode.UNSUPPORTED_SCHEMA)
    entity_versions = manifest["entity_versions"]
    if not isinstance(entity_versions, dict) or entity_versions != ENTITY_VERSIONS or any(
        isinstance(version, bool) or not isinstance(version, int) for version in entity_versions.values()
    ):
        _fail("manifest.entity_versions", "unsupported entity versions", ErrorCode.UNSUPPORTED_SCHEMA)
    if not isinstance(manifest["required_features"], list) or any(
        not isinstance(feature, str) for feature in manifest["required_features"]
    ) or manifest["required_features"] != list(REQUIRED_FEATURES):
        _fail("manifest.required_features", "features must equal the sorted v1 feature set", ErrorCode.UNSUPPORTED_SCHEMA)
    if (
        not isinstance(manifest["scope"], dict)
        or manifest["scope"] != SCOPE
        or not isinstance(manifest["currency"], str)
        or manifest["currency"] != CURRENCY
        or not isinstance(manifest["inventory_semantics"], str)
        or manifest["inventory_semantics"] != INVENTORY_SEMANTICS
    ):
        _fail("manifest", "manifest contains unsupported scope, currency, or inventory semantics")
    counts = _object(manifest["counts"], "manifest.counts")
    _exact_keys(counts, ("products", "product_images", "media_files"), "manifest.counts")
    _integer(counts["products"], "manifest.counts.products", minimum=0, maximum=MAX_PRODUCTS)
    _integer(counts["product_images"], "manifest.counts.product_images", minimum=0, maximum=MAX_PRODUCT_IMAGES)
    _integer(counts["media_files"], "manifest.counts.media_files", minimum=0, maximum=MAX_REGULAR_FILE_ENTRIES)
    if not isinstance(manifest["files"], list):
        _fail("manifest.files", "must be an array")
    for index, descriptor in enumerate(manifest["files"]):
        path = f"manifest.files[{index}]"
        descriptor = _object(descriptor, path)
        _exact_keys(descriptor, FILE_DESCRIPTOR_FIELDS, path)
        file_path = _string(descriptor["path"], f"{path}.path")
        digest = _string(descriptor["sha256"], f"{path}.sha256")
        if not SHA256_PATTERN.fullmatch(digest):
            _fail(f"{path}.sha256", "must be lowercase hexadecimal SHA-256")
        _integer(descriptor["size_bytes"], f"{path}.size_bytes", minimum=0, maximum=TOTAL_UNCOMPRESSED_MEMBER_LIMIT_BYTES)
        if file_path == "catalog.json":
            if descriptor["media_type"] != CATALOG_MEDIA_TYPE:
                _fail(f"{path}.media_type", "catalog.json must be application/json")
        elif not re.fullmatch(r"media/[0-9a-f]{64}\.(?:jpg|png|webp)", file_path) or descriptor["media_type"] not in MEDIA_TYPES:
            _fail(f"{path}", "invalid media file descriptor")
        elif file_path.endswith(".jpg") and descriptor["media_type"] != "image/jpeg":
            _fail(f"{path}.media_type", "extension and media type disagree")
        elif file_path.endswith(".png") and descriptor["media_type"] != "image/png":
            _fail(f"{path}.media_type", "extension and media type disagree")
        elif file_path.endswith(".webp") and descriptor["media_type"] != "image/webp":
            _fail(f"{path}.media_type", "extension and media type disagree")


def decode_json(text: str, *, document: str = "package") -> Any:
    """Decode strict JSON and reject duplicate keys; byte/archive limits are later work."""
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                _fail(document, f"duplicate JSON key {key!r}")
            result[key] = item
        return result

    try:
        return json.loads(text, object_pairs_hook=reject_duplicates, parse_constant=lambda value: _fail(document, f"invalid constant {value}"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SchemaValidationError(ErrorCode.INVALID_PACKAGE, document, "invalid JSON") from exc
