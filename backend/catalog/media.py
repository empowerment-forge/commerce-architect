"""Product-image verification boundary; no database or storage I/O during validation."""

from __future__ import annotations

import hashlib
import io
import warnings
from dataclasses import dataclass

from PIL import Image, ImageFile

from catalog.portability.schema import (
    ErrorCode,
    MAX_IMAGE_BYTES,
    MAX_IMAGE_DIMENSION,
    MAX_IMAGE_PIXELS,
    MEDIA_TYPES,
)
from media_storage.contracts import StoredMedia, StoredMediaBytes
from media_storage.errors import MediaError


FORMAT_INFO = {
    "JPEG": ("image/jpeg", "jpg"),
    "PNG": ("image/png", "png"),
    "WEBP": ("image/webp", "webp"),
}


@dataclass(frozen=True)
class PreparedImage:
    content: bytes
    sha256: str
    size_bytes: int
    content_type: str
    extension: str
    width: int
    height: int

    @property
    def asset_path(self) -> str:
        return f"media/{self.sha256}.{self.extension}"


def _invalid(reason: str, code: ErrorCode = ErrorCode.INVALID_IMAGE):
    raise MediaError(code, reason)


def verify_product_image(content, *, expected=None, asserted_content_type=None) -> PreparedImage:
    if isinstance(content, bytearray):
        content = bytes(content)
    if not isinstance(content, bytes) or not content:
        _invalid("image must be non-empty bytes")
    if len(content) > MAX_IMAGE_BYTES:
        _invalid("encoded image exceeds the limit", ErrorCode.LIMIT_EXCEEDED)
    digest = hashlib.sha256(content).hexdigest()
    size = len(content)
    if expected:
        if expected.get("sha256") != digest or expected.get("size_bytes") != size:
            _invalid("image descriptor does not match bytes", ErrorCode.INVALID_PACKAGE)
        asset_path = expected.get("path") or expected.get("asset_path")
        if asset_path and asset_path != f"media/{digest}.{asset_path.rsplit('.', 1)[-1].lower()}":
            _invalid("image asset path digest does not match bytes", ErrorCode.INVALID_PACKAGE)
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("error")
            with Image.open(io.BytesIO(content)) as image:
                fmt = image.format
                if fmt not in FORMAT_INFO:
                    _invalid("unsupported image format")
                width, height = image.size
                if width <= 0 or height <= 0 or width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION or width * height > MAX_IMAGE_PIXELS:
                    _invalid("image dimensions exceed the limit", ErrorCode.LIMIT_EXCEEDED)
                if getattr(image, "n_frames", 1) != 1:
                    _invalid("animated or multi-frame image")
                image.verify()
            if caught:
                _invalid("image decoder warning")
            with Image.open(io.BytesIO(content)) as image:
                image.load()
                if getattr(image, "n_frames", 1) != 1:
                    _invalid("animated or multi-frame image")
    except MediaError:
        raise
    except Exception as exc:
        _invalid("image decoding failed")
    content_type, extension = FORMAT_INFO[fmt]
    if asserted_content_type is not None and asserted_content_type != content_type:
        _invalid("asserted content type disagrees with image")
    if expected:
        if expected.get("media_type") != content_type or not str(expected.get("path", expected.get("asset_path", ""))).endswith(f".{extension}"):
            _invalid("image descriptor type disagrees with image", ErrorCode.INVALID_PACKAGE)
    return PreparedImage(content, digest, size, content_type, extension, width, height)


def verify_package_images(package):
    descriptors = {item["path"]: item for item in package.manifest["files"]}
    prepared = {}
    for image in package.catalog["product_images"]:
        path = image["asset_path"]
        if path not in prepared:
            descriptor = descriptors.get(path)
            if descriptor is None or path not in package.media:
                _invalid("package image member is missing", ErrorCode.INVALID_PACKAGE)
            prepared[path] = verify_product_image(package.media[path], expected=descriptor)
    return prepared


def store_verified_product_image(adapter, prepared: PreparedImage) -> StoredMedia:
    return adapter.put_if_absent(prepared.content, prepared.content_type)


def read_product_image(adapter, storage_key: str, max_bytes: int) -> tuple[StoredMediaBytes, PreparedImage]:
    stored = adapter.read_verified(storage_key, max_bytes)
    return stored, verify_product_image(stored.content, asserted_content_type=stored.content_type)
