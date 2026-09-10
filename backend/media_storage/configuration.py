from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .delivery import MediaDelivery
from .errors import MediaError
from .local import LocalMediaStorageAdapter
from .s3 import S3CompatibleMediaStorageAdapter
from catalog.portability.schema import ErrorCode


def _required(name):
    value = getattr(settings, name, "")
    if not isinstance(value, str) or not value:
        raise ImproperlyConfigured(f"{name} is required when media is enabled")
    return value


@lru_cache(maxsize=1)
def get_media_storage():
    backend = getattr(settings, "MEDIA_STORAGE_BACKEND", "disabled")
    if backend == "disabled":
        raise MediaError(ErrorCode.OPERATION_NOT_ALLOWED, "media storage is disabled")
    if backend == "local":
        if getattr(settings, "IS_PRODUCTION", False):
            raise ImproperlyConfigured("local media storage is forbidden in production")
        return LocalMediaStorageAdapter(_required("MEDIA_LOCAL_ROOT"))
    if backend == "s3":
        return S3CompatibleMediaStorageAdapter(
            endpoint_url=_required("MEDIA_S3_ENDPOINT_URL"), bucket=_required("MEDIA_S3_BUCKET"),
            region=_required("MEDIA_S3_REGION"), access_key_id=_required("MEDIA_S3_ACCESS_KEY_ID"),
            secret_access_key=_required("MEDIA_S3_SECRET_ACCESS_KEY"), storage_class=getattr(settings, "MEDIA_S3_STORAGE_CLASS", ""),
        )
    raise ImproperlyConfigured("MEDIA_STORAGE_BACKEND must be disabled, local, or s3")


@lru_cache(maxsize=1)
def get_media_delivery():
    return MediaDelivery(_required("MEDIA_PUBLIC_BASE_URL"))


def validate_media_settings():
    backend = getattr(settings, "MEDIA_STORAGE_BACKEND", "disabled")
    if backend not in {"disabled", "local", "s3"}:
        raise ImproperlyConfigured("MEDIA_STORAGE_BACKEND must be disabled, local, or s3")
    if backend == "disabled":
        return
    base = _required("MEDIA_PUBLIC_BASE_URL")
    parsed = urlparse(base)
    if getattr(settings, "IS_PRODUCTION", False) and parsed.scheme != "https":
        raise ImproperlyConfigured("production media delivery requires HTTPS")
    if backend == "local":
        if getattr(settings, "IS_PRODUCTION", False) or not _required("MEDIA_LOCAL_ROOT").startswith("/"):
            raise ImproperlyConfigured("local media is development-only and requires an absolute root")
    if backend == "s3":
        for name in ("MEDIA_S3_ENDPOINT_URL", "MEDIA_S3_BUCKET", "MEDIA_S3_REGION", "MEDIA_S3_ACCESS_KEY_ID", "MEDIA_S3_SECRET_ACCESS_KEY"):
            _required(name)
        if getattr(settings, "MEDIA_S3_STORAGE_CLASS", "") != "STANDARD":
            raise ImproperlyConfigured("MEDIA_S3_STORAGE_CLASS must be STANDARD")
