"""Bounded, non-extracting reader for the Catalog Portability ZIP profile."""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass

from .errors import CatalogPackageError, PackageLimitError, UnsafeArchiveError
from .schema import (
    CATALOG_LIMIT_BYTES,
    ErrorCode,
    MAX_REGULAR_FILE_ENTRIES,
    MAX_JSON_NESTING,
    MANIFEST_LIMIT_BYTES,
    TOTAL_UNCOMPRESSED_MEMBER_LIMIT_BYTES,
    ZIP_FILE_LIMIT_BYTES,
    decode_json,
)
from .schema import SchemaValidationError


@dataclass(frozen=True)
class ArchiveContents:
    members: dict[str, bytes]
    json_members: dict[str, dict]


def _source_bytes(source) -> bytes:
    if isinstance(source, (bytes, bytearray, memoryview)):
        return bytes(source)
    if not hasattr(source, "read"):
        raise UnsafeArchiveError("archive source must be bytes or a readable stream")
    if hasattr(source, "seek"):
        source.seek(0)
    chunks = []
    total = 0
    while True:
        chunk = source.read(min(1024 * 1024, ZIP_FILE_LIMIT_BYTES + 1 - total))
        if not chunk:
            break
        total += len(chunk)
        if total > ZIP_FILE_LIMIT_BYTES:
            raise PackageLimitError("ZIP file limit exceeded")
        chunks.append(chunk)
    return b"".join(chunks)


def _safe_path(path: str) -> bool:
    return (
        path in {"manifest.json", "catalog.json"}
        or re.fullmatch(r"media/[0-9a-f]{64}\.(?:jpg|png|webp)", path) is not None
    )


def _validate_info(info: zipfile.ZipInfo, names: set[str]) -> None:
    path = info.filename
    if path in names:
        raise UnsafeArchiveError("duplicate archive member", path=path)
    if not _safe_path(path) or path != path.replace("\\", "/"):
        raise UnsafeArchiveError("member path is outside the package grammar", path=path)
    file_type = (info.external_attr >> 16) & 0o170000
    if info.is_dir() or file_type not in (0, 0o100000):
        raise UnsafeArchiveError("directories and special files are forbidden", path=path)
    if info.flag_bits & 0x1:
        raise UnsafeArchiveError("encrypted members are forbidden", path=path)
    if info.compress_type != zipfile.ZIP_STORED:
        raise UnsafeArchiveError("compressed members are forbidden", path=path)
    if info.file_size < 0 or info.file_size > TOTAL_UNCOMPRESSED_MEMBER_LIMIT_BYTES:
        raise PackageLimitError("member size limit exceeded", path=path)
    if info.extract_version >= 45 or info.create_version >= 45:
        raise UnsafeArchiveError("ZIP64 members are forbidden", path=path)
    if info.extra or info.comment:
        raise UnsafeArchiveError("member extra fields and comments are forbidden", path=path)
    if any(ord(char) < 32 or ord(char) == 127 for char in path):
        raise UnsafeArchiveError("control characters are forbidden in paths", path=path)
    if path.casefold() in {name.casefold() for name in names}:
        raise UnsafeArchiveError("case-alias archive member", path=path)


def read_archive(source) -> ArchiveContents:
    raw = _source_bytes(source)
    if len(raw) > ZIP_FILE_LIMIT_BYTES:
        raise PackageLimitError("ZIP file limit exceeded")
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw), "r")
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        raise UnsafeArchiveError("invalid ZIP archive") from exc
    with archive:
        if archive.comment:
            raise UnsafeArchiveError("archive comments are forbidden")
        infos = archive.infolist()
        if len(infos) > MAX_REGULAR_FILE_ENTRIES:
            raise PackageLimitError("archive entry limit exceeded")
        names: set[str] = set()
        members: dict[str, bytes] = {}
        total = 0
        for info in infos:
            _validate_info(info, names)
            names.add(info.filename)
            total += info.file_size
            if total > TOTAL_UNCOMPRESSED_MEMBER_LIMIT_BYTES:
                raise PackageLimitError("total uncompressed member limit exceeded")
            with archive.open(info, "r") as member:
                data = member.read(info.file_size + 1)
            if len(data) != info.file_size:
                raise UnsafeArchiveError("member byte count differs from ZIP header", path=info.filename)
            members[info.filename] = data
    for required in ("manifest.json", "catalog.json"):
        if required not in members:
            raise CatalogPackageError(ErrorCode.INVALID_PACKAGE, "required package member is missing", path=required)
    json_members = {}
    for path, limit in (("manifest.json", MANIFEST_LIMIT_BYTES), ("catalog.json", CATALOG_LIMIT_BYTES)):
        if len(members[path]) > limit:
            raise PackageLimitError("JSON member limit exceeded", path=path)
        try:
            json_members[path] = decode_json(members[path].decode("utf-8"), document=path)
        except UnicodeDecodeError as exc:
            raise CatalogPackageError(ErrorCode.INVALID_PACKAGE, "JSON member is not UTF-8", path=path) from exc
        except SchemaValidationError as exc:
            raise CatalogPackageError(exc.code, exc.message, path=exc.path) from exc
        if _json_depth(json_members[path]) > MAX_JSON_NESTING:
            raise PackageLimitError("JSON nesting limit exceeded", path=path)
    return ArchiveContents(members=members, json_members=json_members)


def _json_depth(value) -> int:
    if isinstance(value, dict):
        return 1 + max((_json_depth(item) for item in value.values()), default=0)
    if isinstance(value, list):
        return 1 + max((_json_depth(item) for item in value), default=0)
    return 0
