"""Stable errors for the pure catalog package codec and archive reader."""

from __future__ import annotations

from catalog.portability.schema import ErrorCode


class CatalogPackageError(ValueError):
    """A package error with a stable v1 code and useful location."""

    def __init__(self, code: ErrorCode, message: str, *, path: str | None = None):
        self.code = code
        self.path = path
        self.message = message
        location = f" at {path}" if path else ""
        super().__init__(f"{code}{location}: {message}")


class UnsafeArchiveError(CatalogPackageError):
    def __init__(self, message: str, *, path: str | None = None):
        super().__init__(ErrorCode.UNSAFE_ARCHIVE, message, path=path)


class PackageLimitError(CatalogPackageError):
    def __init__(self, message: str, *, path: str | None = None):
        super().__init__(ErrorCode.LIMIT_EXCEEDED, message, path=path)
