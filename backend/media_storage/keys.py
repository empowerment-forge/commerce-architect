from __future__ import annotations

import hashlib
import re

from catalog.portability.schema import ErrorCode
from .errors import MediaError


STORAGE_KEY_PATTERN = re.compile(r"sha256/[0-9a-f]{64}\Z")


def validate_storage_key(storage_key: str) -> str:
    if not isinstance(storage_key, str) or not STORAGE_KEY_PATTERN.fullmatch(storage_key):
        raise MediaError(ErrorCode.OPERATION_NOT_ALLOWED, "invalid storage key")
    return storage_key


def storage_key_for_bytes(content: bytes) -> tuple[str, str]:
    if not isinstance(content, bytes) or not content:
        raise MediaError(ErrorCode.INVALID_IMAGE, "media content must be non-empty bytes")
    digest = hashlib.sha256(content).hexdigest()
    return f"sha256/{digest}", digest
