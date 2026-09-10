from __future__ import annotations

from urllib.parse import urlparse

from .keys import validate_storage_key
from .errors import MediaError
from catalog.portability.schema import ErrorCode


class MediaDelivery:
    def __init__(self, base_url: str):
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.query or parsed.fragment or parsed.username:
            raise MediaError(ErrorCode.OPERATION_NOT_ALLOWED, "invalid media public base URL")
        self.base_url = base_url.rstrip("/")

    def public_url(self, storage_key: str) -> str:
        validate_storage_key(storage_key)
        return f"{self.base_url}/{storage_key}"
