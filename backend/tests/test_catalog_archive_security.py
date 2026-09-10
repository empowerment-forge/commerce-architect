import io
import zipfile

import pytest

from catalog.portability.archive import read_archive
from catalog.portability.codec import canonical_json_bytes
from catalog.portability.errors import CatalogPackageError
from catalog.portability.schema import ErrorCode


def zip_bytes(entries, *, compression=zipfile.ZIP_STORED):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=compression) as archive:
        for name, content in entries:
            archive.writestr(name, content)
    return output.getvalue()


def valid_json_entries():
    return [("manifest.json", canonical_json_bytes({})), ("catalog.json", b'{"products":[],"product_images":[]}\n')]


@pytest.mark.parametrize("name", ["../catalog.json", "/catalog.json", "media/../catalog.json", "media\\x.jpg", "C:/catalog.json", "//server/catalog.json"])
def test_path_traversal_and_alias_forms_are_rejected(name):
    with pytest.raises(CatalogPackageError) as error:
        read_archive(zip_bytes([(name, b"x")]))
    assert error.value.code == ErrorCode.UNSAFE_ARCHIVE


def test_compressed_members_are_rejected():
    with pytest.raises(CatalogPackageError) as error:
        read_archive(zip_bytes(valid_json_entries(), compression=zipfile.ZIP_DEFLATED))
    assert error.value.code == ErrorCode.UNSAFE_ARCHIVE


def test_duplicate_and_case_alias_members_are_rejected():
    entries = [("catalog.json", b"{}"), ("CATALOG.JSON", b"{}")]
    with pytest.raises(CatalogPackageError) as error:
        read_archive(zip_bytes(entries))
    assert error.value.code == ErrorCode.UNSAFE_ARCHIVE


def test_symlink_member_is_rejected():
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        info = zipfile.ZipInfo("catalog.json")
        info.external_attr = 0o120777 << 16
        archive.writestr(info, b"{}")
    with pytest.raises(CatalogPackageError) as error:
        read_archive(output.getvalue())
    assert error.value.code == ErrorCode.UNSAFE_ARCHIVE


def test_required_members_are_checked_without_extracting():
    with pytest.raises(CatalogPackageError) as error:
        read_archive(zip_bytes([]))
    assert error.value.code == ErrorCode.INVALID_PACKAGE


def test_stored_regular_members_can_be_read_without_extraction():
    contents = read_archive(zip_bytes(valid_json_entries()))
    assert set(contents.members) == {"manifest.json", "catalog.json"}
