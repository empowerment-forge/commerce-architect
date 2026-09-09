import json
from pathlib import Path

import pytest

from catalog.portability.schema import (
    CATALOG_MEDIA_TYPE,
    ENTITY_VERSIONS,
    ErrorCode,
    FORMAT,
    FORMAT_VERSION,
    SchemaValidationError,
    decode_json,
    validate_catalog,
    validate_manifest,
)


FIXTURES = Path(__file__).parent / "fixtures" / "catalog_portability"


def load_fixture(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "fixture",
    [
        "valid/empty_catalog.json",
        "valid/product_without_images.json",
        "valid/shared_image_binary.json",
        "valid/boundary_values.json",
    ],
)
def test_valid_catalog_fixtures(fixture):
    validate_catalog(load_fixture(FIXTURES / fixture))


@pytest.mark.parametrize(
    "fixture,code",
    [
        ("invalid/unknown_product_field.json", ErrorCode.INVALID_PACKAGE),
        ("invalid/duplicate_product_id.json", ErrorCode.DUPLICATE_ID),
        ("invalid/float_stock.json", ErrorCode.INVALID_PACKAGE),
        ("invalid/boolean_stock.json", ErrorCode.INVALID_PACKAGE),
    ],
)
def test_invalid_catalog_fixtures_have_stable_codes(fixture, code):
    with pytest.raises(SchemaValidationError) as error:
        validate_catalog(load_fixture(FIXTURES / fixture))
    assert error.value.code == code


def test_required_constants_are_frozen():
    assert FORMAT == "commerce-architect-catalog"
    assert FORMAT_VERSION == 1
    assert ENTITY_VERSIONS == {"product": 1, "product_image": 1}
    assert CATALOG_MEDIA_TYPE == "application/json"


def test_manifest_rejects_unknown_feature_and_accepts_exact_contract():
    manifest = load_fixture(FIXTURES / "invalid/unknown_feature_manifest.json")
    with pytest.raises(SchemaValidationError) as error:
        validate_manifest(manifest)
    assert error.value.code == ErrorCode.UNSUPPORTED_SCHEMA

    manifest["required_features"].pop()
    validate_manifest(manifest)


def test_manifest_rejects_unknown_version():
    manifest = load_fixture(FIXTURES / "invalid/unknown_version_manifest.json")
    with pytest.raises(SchemaValidationError) as error:
        validate_manifest(manifest)
    assert error.value.code == ErrorCode.UNSUPPORTED_SCHEMA


def test_json_decoder_rejects_duplicate_keys_and_non_json_numbers():
    with pytest.raises(SchemaValidationError) as duplicate:
        decode_json('{"products": [], "products": []}', document="catalog.json")
    assert duplicate.value.code == ErrorCode.INVALID_PACKAGE

    with pytest.raises(SchemaValidationError) as nan:
        decode_json('{"value": NaN}', document="catalog.json")
    assert nan.value.code == ErrorCode.INVALID_PACKAGE


@pytest.mark.parametrize(
    "field,value",
    [
        ("price", "00.00"),
        ("price", "1.0"),
        ("price", "1e2"),
        ("sku", "lowercase"),
        ("status", "pending"),
    ],
)
def test_exact_scalar_contract_boundaries(field, value):
    catalog = load_fixture(FIXTURES / "valid/product_without_images.json")
    catalog["products"][0][field] = value
    with pytest.raises(SchemaValidationError):
        validate_catalog(catalog)
