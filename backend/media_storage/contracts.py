from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class StoredMedia:
    storage_key: str
    sha256: str
    size_bytes: int
    content_type: str


@dataclass(frozen=True)
class StoredMediaBytes(StoredMedia):
    content: bytes


class MediaStorageAdapter(Protocol):
    def put_if_absent(self, content: bytes, content_type: str) -> StoredMedia: ...

    def read_verified(self, storage_key: str, max_bytes: int) -> StoredMediaBytes: ...
