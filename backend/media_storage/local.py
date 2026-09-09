from __future__ import annotations

import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

import fcntl

from catalog.portability.schema import ErrorCode, MEDIA_TYPES
from .contracts import StoredMedia, StoredMediaBytes
from .errors import MediaError
from .keys import storage_key_for_bytes, validate_storage_key


CONTENT_DISPOSITION = "inline"
CACHE_CONTROL = "public, max-age=31536000, immutable"


class LocalMediaStorageAdapter:
    def __init__(self, root: str | os.PathLike):
        self.root = Path(root)
        if not self.root.is_absolute():
            raise MediaError(ErrorCode.OPERATION_NOT_ALLOWED, "local media root must be absolute")
        self.root.mkdir(parents=True, exist_ok=True)
        self._ensure_directory(self.root)
        (self.root / ".locks").mkdir(mode=0o700, exist_ok=True)
        self._ensure_directory(self.root / ".locks")

    @staticmethod
    def _ensure_directory(path: Path):
        stat = path.lstat()
        if not path.is_dir() or path.is_symlink():
            raise MediaError(ErrorCode.MEDIA_UNAVAILABLE, "media root contains an unsafe path")
        if stat.st_mode & 0o002:
            raise MediaError(ErrorCode.MEDIA_UNAVAILABLE, "media root is world writable")

    def _key_path(self, key: str) -> Path:
        validate_storage_key(key)
        digest = key.split("/", 1)[1]
        path = self.root / "sha256" / digest
        if path.parent.exists():
            self._ensure_directory(path.parent)
        return path

    @contextmanager
    def _lock(self, digest: str):
        lock_path = self.root / ".locks" / f"{digest}.lock"
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _read_unlocked(self, key: str, max_bytes: int) -> StoredMediaBytes:
        path = self._key_path(key)
        if not path.exists() or path.is_symlink() or not path.is_dir():
            raise MediaError(ErrorCode.MEDIA_UNAVAILABLE, "media object is unavailable")
        content_path = path / "content"
        metadata_path = path / "metadata.json"
        if content_path.is_symlink() or metadata_path.is_symlink():
            raise MediaError(ErrorCode.MEDIA_UNAVAILABLE, "media object contains a symlink")
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            content = content_path.read_bytes()
        except (OSError, ValueError, UnicodeError) as exc:
            raise MediaError(ErrorCode.MEDIA_UNAVAILABLE, "media object cannot be read") from exc
        if len(content) > max_bytes or len(content) != metadata.get("size_bytes"):
            raise MediaError(ErrorCode.MEDIA_UNAVAILABLE, "media object exceeds read bound or has wrong length")
        digest = hashlib.sha256(content).hexdigest()
        if key != f"sha256/{digest}" or metadata.get("sha256") != digest or metadata.get("content_type") not in MEDIA_TYPES:
            raise MediaError(ErrorCode.MEDIA_UNAVAILABLE, "media object integrity metadata is invalid")
        return StoredMediaBytes(key, digest, len(content), metadata["content_type"], content)

    def put_if_absent(self, content: bytes, content_type: str) -> StoredMedia:
        if content_type not in MEDIA_TYPES:
            raise MediaError(ErrorCode.INVALID_IMAGE, "unsupported media content type")
        key, digest = storage_key_for_bytes(bytes(content))
        with self._lock(digest):
            final = self._key_path(key)
            if final.exists() or final.is_symlink():
                existing = self._read_unlocked(key, len(content))
                if existing.content == content and existing.content_type == content_type:
                    return StoredMedia(key, digest, len(content), content_type)
                raise MediaError(ErrorCode.MEDIA_UNAVAILABLE, "existing media differs")
            (self.root / "sha256").mkdir(mode=0o700, exist_ok=True)
            temp = Path(tempfile.mkdtemp(prefix=".staging-", dir=self.root / "sha256"))
            try:
                content_path = temp / "content"
                metadata_path = temp / "metadata.json"
                with content_path.open("xb") as handle:
                    handle.write(content); handle.flush(); os.fsync(handle.fileno())
                metadata = {"content_type": content_type, "sha256": digest, "size_bytes": len(content)}
                with metadata_path.open("x", encoding="utf-8") as handle:
                    json.dump(metadata, handle, sort_keys=True, separators=(",", ":")); handle.flush(); os.fsync(handle.fileno())
                os.chmod(content_path, 0o600); os.chmod(metadata_path, 0o600)
                temp_fd = os.open(temp, os.O_RDONLY)
                try:
                    os.fsync(temp_fd)
                finally:
                    os.close(temp_fd)
                os.rename(temp, final)
                directory = os.open(final.parent, os.O_RDONLY); os.fsync(directory); os.close(directory)
            except Exception as exc:
                if temp.exists():
                    for child in temp.iterdir(): child.unlink()
                    temp.rmdir()
                raise MediaError(ErrorCode.MEDIA_UNAVAILABLE, "media publication failed") from exc
        verified = self.read_verified(key, len(content))
        if verified.content != content or verified.content_type != content_type:
            raise MediaError(ErrorCode.MEDIA_UNAVAILABLE, "media readback differs")
        return StoredMedia(key, verified.sha256, verified.size_bytes, verified.content_type)

    def read_verified(self, storage_key: str, max_bytes: int) -> StoredMediaBytes:
        if not isinstance(max_bytes, int) or max_bytes <= 0:
            raise MediaError(ErrorCode.OPERATION_NOT_ALLOWED, "max_bytes must be positive")
        digest = validate_storage_key(storage_key).split("/", 1)[1]
        with self._lock(digest):
            return self._read_unlocked(storage_key, max_bytes)
