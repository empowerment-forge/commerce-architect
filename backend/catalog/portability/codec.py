"""Pure canonical JSON and ZIP codec for Catalog Portability v1."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import dataclass
from typing import Mapping

from .errors import CatalogPackageError
from .schema import (
    CATALOG_LIMIT_BYTES,
    ErrorCode,
    MANIFEST_LIMIT_BYTES,
    MAX_REGULAR_FILE_ENTRIES,
    TOTAL_UNCOMPRESSED_MEMBER_LIMIT_BYTES,
    validate_catalog,
    validate_manifest,
)
from .archive import read_archive


@dataclass(frozen=True)
class CatalogPackage:
    manifest: dict
    catalog: dict
    media: dict[str, bytes]


def canonical_json_bytes(value: object) -> bytes:
    """Serialize JSON with v1's stable UTF-8 representation."""
    def reject_noncanonical(item):
        if isinstance(item, float):
            raise ValueError("floating-point values are not permitted")
        if isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                raise ValueError("object keys must be strings")
            for child in item.values():
                reject_noncanonical(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                reject_noncanonical(child)

    try:
        reject_noncanonical(value)
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        encoded = (text + "\n").encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise CatalogPackageError(ErrorCode.INVALID_PACKAGE, "value is not canonical JSON") from exc
    return encoded


def _descriptor_map(manifest: dict) -> dict[str, dict]:
    result = {}
    for descriptor in manifest["files"]:
        path = descriptor["path"]
        if path in result:
            raise CatalogPackageError(ErrorCode.INVALID_PACKAGE, "duplicate manifest file path", path=path)
        result[path] = descriptor
    return result


def encode_package(manifest: dict, catalog: dict, media: Mapping[str, bytes]) -> bytes:
    """Build canonical stored-only ZIP bytes without accessing Django or storage."""
    validate_manifest(manifest)
    validate_catalog(catalog)
    catalog_bytes = canonical_json_bytes(catalog)
    manifest_bytes = canonical_json_bytes(manifest)
    if len(manifest_bytes) > MANIFEST_LIMIT_BYTES:
        raise CatalogPackageError(ErrorCode.LIMIT_EXCEEDED, "manifest exceeds its byte limit")
    if len(catalog_bytes) > CATALOG_LIMIT_BYTES:
        raise CatalogPackageError(ErrorCode.LIMIT_EXCEEDED, "catalog exceeds its byte limit")

    descriptors = _descriptor_map(manifest)
    expected = {"manifest.json": manifest_bytes, "catalog.json": catalog_bytes}
    for path, content in media.items():
        if path in expected or not isinstance(path, str) or not isinstance(content, bytes):
            raise CatalogPackageError(ErrorCode.INVALID_PACKAGE, "invalid media member", path=path)
        expected[path] = content
    if set(descriptors) != (set(expected) - {"manifest.json"}):
        raise CatalogPackageError(ErrorCode.INVALID_PACKAGE, "manifest and package members differ")
    referenced_media = {image["asset_path"] for image in catalog["product_images"]}
    if referenced_media != set(media):
        raise CatalogPackageError(ErrorCode.INVALID_PACKAGE, "catalog and media members differ")
    if manifest["counts"] != {
        "products": len(catalog["products"]),
        "product_images": len(catalog["product_images"]),
        "media_files": len(media),
    }:
        raise CatalogPackageError(ErrorCode.INVALID_PACKAGE, "manifest counts do not match catalog")
    total = 0
    for path, content in expected.items():
        descriptor = descriptors.get(path)
        if path != "manifest.json" and descriptor is None:
            raise CatalogPackageError(ErrorCode.INVALID_PACKAGE, "member missing from manifest", path=path)
        if path == "manifest.json":
            continue
        if len(content) != descriptor["size_bytes"] or hashlib.sha256(content).hexdigest() != descriptor["sha256"]:
            raise CatalogPackageError(ErrorCode.INVALID_PACKAGE, "member size or hash does not match", path=path)
        total += len(content)
    if total > TOTAL_UNCOMPRESSED_MEMBER_LIMIT_BYTES:
        raise CatalogPackageError(ErrorCode.LIMIT_EXCEEDED, "total member bytes exceed the limit")

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED, allowZip64=False) as archive:
        for path in ("manifest.json", "catalog.json", *sorted(path for path in media)):
            info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.create_version = 20
            info.extract_version = 20
            info.flag_bits = 0
            info.internal_attr = 0
            info.external_attr = 0o100600 << 16
            archive.writestr(info, expected[path])
    package = output.getvalue()
    from .schema import ZIP_FILE_LIMIT_BYTES
    if len(package) > ZIP_FILE_LIMIT_BYTES:
        raise CatalogPackageError(ErrorCode.LIMIT_EXCEEDED, "ZIP exceeds the limit")
    return package


def decode_package(source) -> CatalogPackage:
    """Decode and validate a bounded package from bytes or a seekable stream."""
    archive = read_archive(source)
    manifest = archive.json_members["manifest.json"]
    catalog = archive.json_members["catalog.json"]
    validate_manifest(manifest)
    validate_catalog(catalog)
    descriptors = _descriptor_map(manifest)
    actual_media = {path: data for path, data in archive.members.items() if path.startswith("media/")}
    expected = {path for path in descriptors if path not in {"manifest.json", "catalog.json"}}
    if expected != set(actual_media):
        raise CatalogPackageError(ErrorCode.INVALID_PACKAGE, "manifest and archive media differ")
    referenced_media = {image["asset_path"] for image in catalog["product_images"]}
    if referenced_media != set(actual_media):
        raise CatalogPackageError(ErrorCode.INVALID_PACKAGE, "catalog and media members differ")
    if manifest["counts"] != {
        "products": len(catalog["products"]),
        "product_images": len(catalog["product_images"]),
        "media_files": len(actual_media),
    }:
        raise CatalogPackageError(ErrorCode.INVALID_PACKAGE, "manifest counts do not match archive")
    for path, content in archive.members.items():
        if path == "manifest.json":
            continue
        descriptor = descriptors.get(path)
        if descriptor is None or descriptor["size_bytes"] != len(content) or descriptor["sha256"] != hashlib.sha256(content).hexdigest():
            raise CatalogPackageError(ErrorCode.INVALID_PACKAGE, "member does not match manifest", path=path)
    return CatalogPackage(manifest=manifest, catalog=catalog, media=actual_media)
