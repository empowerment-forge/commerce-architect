import hashlib

import pytest

from catalog.portability.schema import ErrorCode
from media_storage.delivery import MediaDelivery
from media_storage.errors import MediaError
from media_storage.keys import storage_key_for_bytes, validate_storage_key


def test_content_addressed_key_is_extension_free_and_stable():
    content = b"immutable"
    key, digest = storage_key_for_bytes(content)
    assert digest == hashlib.sha256(content).hexdigest()
    assert key == f"sha256/{digest}"
    assert validate_storage_key(key) == key


@pytest.mark.parametrize("key", ["/sha256/" + "a" * 64, "sha256/" + "A" * 64, "sha256/../x", "sha256/" + "a" * 63, "sha256/" + "a" * 64 + "?x"])
def test_invalid_keys_fail_closed(key):
    with pytest.raises(MediaError) as error:
        validate_storage_key(key)
    assert error.value.code == ErrorCode.OPERATION_NOT_ALLOWED


def test_public_url_is_pure_and_cannot_change_host():
    delivery = MediaDelivery("https://media.example.test/media")
    key = "sha256/" + "a" * 64
    assert delivery.public_url(key) == f"https://media.example.test/media/{key}"
    with pytest.raises(MediaError):
        delivery.public_url("https://evil.example/" + key)
