import hashlib
import io
import json
import zipfile

import pytest

from catalog.portability.codec import canonical_json_bytes, decode_package, encode_package
from catalog.portability.errors import CatalogPackageError
from catalog.portability.schema import ErrorCode


PRODUCT_ID = "00000000-0000-4000-8000-000000000001"
IMAGE_PATH = "media/" + "a" * 64 + ".jpg"


def catalog_fixture():
    return {
        "products": [{
            "portable_id": PRODUCT_ID,
            "sku": "SKU-001",
            "name": "Portable Product",
            "description": "",
            "price": "10.00",
            "stock_quantity": 0,
            "status": "active",
        }],
        "product_images": [],
    }


def manifest_fixture(catalog, media):
    files = [{
        "path": "catalog.json",
        "sha256": hashlib.sha256(canonical_json_bytes(catalog)).hexdigest(),
        "size_bytes": len(canonical_json_bytes(catalog)),
        "media_type": "application/json",
    }]
    for path, content in media.items():
        files.append({
            "path": path,
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
            "media_type": "image/jpeg",
        })
    return {
        "format": "commerce-architect-catalog",
        "format_version": 1,
        "domain_schema": "product-commerce-catalog/1",
        "entity_versions": {"product": 1, "product_image": 1},
        "required_features": ["embedded-images", "organization-scope", "portable-identities", "stock-snapshot"],
        "scope": {"kind": "organization", "coverage": "full"},
        "currency": "USD",
        "inventory_semantics": "snapshot-not-reservation",
        "counts": {"products": len(catalog["products"]), "product_images": len(catalog["product_images"]), "media_files": len(media)},
        "files": files,
    }


def test_canonical_json_is_stable_and_has_one_trailing_lf():
    assert canonical_json_bytes({"z": 1, "a": "é"}) == '{"a":"é","z":1}\n'.encode("utf-8")


def test_package_round_trip_is_byte_identical_across_input_mapping_order():
    catalog = catalog_fixture()
    media = {IMAGE_PATH: b"same image bytes"}
    catalog["product_images"].append({
        "portable_id": "00000000-0000-4000-8000-000000000011",
        "product_portable_id": PRODUCT_ID,
        "asset_path": IMAGE_PATH,
        "alt_text": "",
        "sort_order": 0,
        "is_primary": True,
    })
    manifest = manifest_fixture(catalog, media)
    package = encode_package(manifest, catalog, media)
    assert package == encode_package(dict(reversed(manifest.items())), dict(reversed(catalog.items())), dict(reversed(list(media.items()))))
    decoded = decode_package(io.BytesIO(package))
    assert decoded.catalog == catalog
    assert decoded.media == media


def test_canonical_zip_header_golden_attributes():
    catalog = {"products": [], "product_images": []}
    media = {}
    package = encode_package(manifest_fixture(catalog, media), catalog, media)
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        assert archive.namelist() == ["manifest.json", "catalog.json"]
        for info in archive.infolist():
            assert info.date_time == (1980, 1, 1, 0, 0, 0)
            assert info.compress_type == zipfile.ZIP_STORED
            assert info.create_system == 3
            assert info.create_version == 20
            assert info.extract_version == 20
            assert info.flag_bits == 0
            assert info.internal_attr == 0
            assert info.external_attr == 0o100600 << 16
            assert not info.extra
            assert not info.comment


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), "\ud800"])
def test_non_canonical_json_values_are_rejected(bad):
    with pytest.raises(CatalogPackageError):
        canonical_json_bytes({"bad": bad})


def test_package_rejects_manifest_hash_mismatch():
    catalog = catalog_fixture()
    manifest = manifest_fixture(catalog, {})
    manifest["files"][0]["sha256"] = "0" * 64
    with pytest.raises(CatalogPackageError) as error:
        encode_package(manifest, catalog, {})
    assert error.value.code == ErrorCode.INVALID_PACKAGE
