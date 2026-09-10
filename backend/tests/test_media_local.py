import multiprocessing

import pytest

from media_storage.errors import MediaError
from media_storage.local import LocalMediaStorageAdapter


def test_local_adapter_persists_and_reuses_exact_bytes(tmp_path):
    adapter = LocalMediaStorageAdapter(tmp_path / "media")
    content = b"local immutable bytes"
    first = adapter.put_if_absent(content, "image/png")
    second = adapter.put_if_absent(bytearray(content), "image/png")
    assert first == second
    assert adapter.read_verified(first.storage_key, len(content)).content == content


def test_local_adapter_rejects_different_content_at_existing_key(tmp_path):
    adapter = LocalMediaStorageAdapter(tmp_path / "media")
    first = adapter.put_if_absent(b"one", "image/png")
    (tmp_path / "media" / "sha256" / first.sha256 / "content").write_bytes(b"two")
    with pytest.raises(MediaError):
        adapter.put_if_absent(b"one", "image/png")
    with pytest.raises(MediaError):
        adapter.read_verified(first.storage_key, 3)


def test_local_adapter_rejects_symlink_object(tmp_path):
    root = tmp_path / "media"
    adapter = LocalMediaStorageAdapter(root)
    stored = adapter.put_if_absent(b"safe", "image/png")
    path = root / "sha256" / stored.sha256
    (path / "content").unlink()
    (path / "content").symlink_to(tmp_path / "outside")
    with pytest.raises(MediaError):
        adapter.read_verified(stored.storage_key, 10)
