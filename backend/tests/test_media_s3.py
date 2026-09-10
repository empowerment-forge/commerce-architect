import hashlib
from botocore.exceptions import ClientError

import pytest

from media_storage.errors import MediaError
from media_storage.s3 import S3CompatibleMediaStorageAdapter


class FakeBody:
    def __init__(self, content):
        self.content = content

    def read(self, size=-1):
        return self.content if size < 0 else self.content[:size]


class FakeS3:
    def __init__(self, content=b"r2 bytes"):
        self.content = content
        self.puts = []

    def put_object(self, **kwargs):
        self.puts.append(kwargs)

    def get_object(self, **kwargs):
        return {"Body": FakeBody(self.content), "ContentLength": len(self.content), "ContentType": "image/png", "ContentDisposition": "inline", "CacheControl": "public, max-age=31536000, immutable"}


def adapter(client):
    return S3CompatibleMediaStorageAdapter(endpoint_url="https://r2.example", bucket="media", region="auto", access_key_id="key", secret_access_key="secret", client=client)


def test_s3_put_uses_conditional_immutable_request_and_origin_readback():
    client = FakeS3(b"r2 bytes")
    content = client.content
    stored = adapter(client).put_if_absent(content, "image/png")
    request = client.puts[0]
    assert stored.sha256 == hashlib.sha256(content).hexdigest()
    assert request["IfNoneMatch"] == "*"
    assert request["ContentLength"] == len(content)
    assert request["ContentType"] == "image/png"
    assert request["ContentDisposition"] == "inline"
    assert request["CacheControl"] == "public, max-age=31536000, immutable"
    assert request["StorageClass"] == "STANDARD"


def test_s3_read_rejects_wrong_origin_content():
    client = FakeS3(b"wrong")
    key = "sha256/" + hashlib.sha256(b"expected").hexdigest()
    with pytest.raises(MediaError):
        adapter(client).read_verified(key, 100)
