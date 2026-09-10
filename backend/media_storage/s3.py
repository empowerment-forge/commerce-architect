from __future__ import annotations

import base64
import hashlib
import time

from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from catalog.portability.schema import ErrorCode, MEDIA_TYPES
from .contracts import StoredMedia, StoredMediaBytes
from .errors import MediaError
from .keys import storage_key_for_bytes, validate_storage_key


CACHE_CONTROL = "public, max-age=31536000, immutable"


class S3CompatibleMediaStorageAdapter:
    def __init__(self, *, endpoint_url, bucket, region, access_key_id, secret_access_key, storage_class="STANDARD", client=None, sleep=time.sleep):
        if not all(isinstance(value, str) and value for value in (endpoint_url, bucket, region, access_key_id, secret_access_key)) or storage_class != "STANDARD":
            raise MediaError(ErrorCode.OPERATION_NOT_ALLOWED, "incomplete S3 media configuration")
        self.bucket = bucket
        self.sleep = sleep
        if client is None:
            import boto3
            client = boto3.client(
                "s3", endpoint_url=endpoint_url, region_name=region,
                aws_access_key_id=access_key_id, aws_secret_access_key=secret_access_key,
                config=Config(signature_version="s3v4", s3={"addressing_style": "path"}, retries={"max_attempts": 1, "mode": "standard"}, connect_timeout=5, read_timeout=30),
            )
        self.client = client

    @staticmethod
    def _error_code(exc):
        return str(exc.response.get("Error", {}).get("Code", "")) if isinstance(exc, ClientError) else ""

    def _read(self, key: str, max_bytes: int):
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            body = response["Body"].read(max_bytes + 1)
            if len(body) > max_bytes:
                raise MediaError(ErrorCode.MEDIA_UNAVAILABLE, "media object exceeds read bound")
            content_type = response.get("ContentType")
            if content_type not in MEDIA_TYPES or response.get("ContentDisposition") != "inline" or response.get("CacheControl") != CACHE_CONTROL:
                raise MediaError(ErrorCode.MEDIA_UNAVAILABLE, "media object metadata is invalid")
            digest = hashlib.sha256(body).hexdigest()
            if key != f"sha256/{digest}" or response.get("ContentLength") != len(body):
                raise MediaError(ErrorCode.MEDIA_UNAVAILABLE, "media object integrity is invalid")
            return StoredMediaBytes(key, digest, len(body), content_type, body)
        except MediaError:
            raise
        except (BotoCoreError, ClientError, KeyError) as exc:
            raise MediaError(ErrorCode.MEDIA_UNAVAILABLE, "media origin read failed") from exc

    def read_verified(self, storage_key: str, max_bytes: int) -> StoredMediaBytes:
        if not isinstance(max_bytes, int) or max_bytes <= 0:
            raise MediaError(ErrorCode.OPERATION_NOT_ALLOWED, "max_bytes must be positive")
        return self._read(validate_storage_key(storage_key), max_bytes)

    def put_if_absent(self, content: bytes, content_type: str) -> StoredMedia:
        if content_type not in MEDIA_TYPES:
            raise MediaError(ErrorCode.INVALID_IMAGE, "unsupported media content type")
        content = bytes(content)
        key, digest = storage_key_for_bytes(content)
        request = {
            "Bucket": self.bucket, "Key": key, "Body": content,
            "ContentLength": len(content), "ContentType": content_type,
            "ContentDisposition": "inline", "CacheControl": CACHE_CONTROL,
            "StorageClass": "STANDARD", "IfNoneMatch": "*",
            "ContentMD5": base64.b64encode(hashlib.md5(content, usedforsecurity=False).digest()).decode("ascii"),
        }
        delays = (0, 0.1, 0.5)
        for attempt, delay in enumerate(delays):
            if delay:
                self.sleep(delay)
            try:
                self.client.put_object(**request)
            except (BotoCoreError, ClientError) as exc:
                code = self._error_code(exc)
                try:
                    existing = self._read(key, len(content))
                    if existing.content == content and existing.content_type == content_type:
                        return StoredMedia(key, digest, len(content), content_type)
                    raise MediaError(ErrorCode.MEDIA_UNAVAILABLE, "existing media differs")
                except MediaError as read_error:
                    if code in {"404", "NoSuchKey", "NotFound", "412", "PreconditionFailed", "409", "Conflict", "500", "503"} and attempt < len(delays) - 1:
                        continue
                    if code in {"403", "AccessDenied"}:
                        raise MediaError(ErrorCode.MEDIA_UNAVAILABLE, "media write is not authorized") from exc
                    if read_error.code == ErrorCode.MEDIA_UNAVAILABLE and attempt == len(delays) - 1:
                        raise MediaError(ErrorCode.MEDIA_UNAVAILABLE, "write_outcome_unknown") from exc
                    continue
            verified = self._read(key, len(content))
            if verified.content != content or verified.content_type != content_type:
                raise MediaError(ErrorCode.MEDIA_UNAVAILABLE, "media readback differs")
            return StoredMedia(key, digest, len(content), content_type)
        raise MediaError(ErrorCode.MEDIA_UNAVAILABLE, "write_outcome_unknown")
