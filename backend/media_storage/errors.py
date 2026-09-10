from __future__ import annotations

from catalog.portability.schema import ErrorCode


class MediaError(RuntimeError):
    def __init__(self, code: ErrorCode, reason: str):
        self.code = code
        self.reason = reason
        super().__init__(f"{code}: {reason}")
