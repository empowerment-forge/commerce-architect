"""Shared boundary helpers for trusted Catalog Portability commands."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Callable

from django.conf import settings
from django.core.management.base import CommandError

from catalog.models import CatalogOperationReceipt
from catalog.portability.errors import CatalogPackageError
from catalog.portability.schema import ErrorCode, ZIP_FILE_LIMIT_BYTES
from catalog.services import CatalogBusyError, CatalogScopeError


class CatalogCommandError(CommandError):
    def __init__(self, message: str, *, returncode: int):
        super().__init__(message, returncode=returncode)


def ensure_enabled() -> None:
    if not getattr(settings, "CATALOG_PORTABILITY_ENABLED", False):
        raise CatalogCommandError(
            "Catalog Portability operator commands are disabled.",
            returncode=4,
        )


def read_bounded_input(path: str) -> bytes:
    input_path = Path(path)
    if not input_path.is_file():
        raise CatalogCommandError(
            "input package must be an existing regular file",
            returncode=2,
        )
    try:
        with input_path.open("rb") as handle:
            content = handle.read(ZIP_FILE_LIMIT_BYTES + 1)
    except OSError as exc:
        raise CatalogCommandError(
            "input package could not be read",
            returncode=5,
        ) from exc
    if len(content) > ZIP_FILE_LIMIT_BYTES:
        raise CatalogCommandError("input package exceeds the ZIP limit", returncode=2)
    return content


def parse_operation_id(value) -> uuid.UUID:
    try:
        operation_id = value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise CatalogCommandError("operation ID must be a UUIDv4", returncode=2) from exc
    if operation_id.version != 4:
        raise CatalogCommandError("operation ID must be a UUIDv4", returncode=2)
    return operation_id


def write_json(command, value: dict[str, Any]) -> None:
    command.stdout.write(json.dumps(value, sort_keys=True, separators=(",", ":")))


def receipt_payload(receipt: CatalogOperationReceipt) -> dict[str, Any]:
    return {
        "status": "successful",
        "operation_id": str(receipt.operation_id),
        "organization_id": receipt.organization_id,
        "operation_type": receipt.operation_type,
        "package_sha256": receipt.package_sha256,
        "inventory_policy": receipt.inventory_policy,
        "expected_catalog_digest": receipt.expected_catalog_digest,
        "pre_catalog_digest": receipt.pre_catalog_digest,
        "post_catalog_digest": receipt.post_catalog_digest,
        "result_counts": receipt.result_counts,
        "completed_at": receipt.completed_at.isoformat(),
    }


def command_error_for(exc: Exception) -> CatalogCommandError:
    if isinstance(exc, CatalogCommandError):
        return exc
    if isinstance(exc, CatalogScopeError):
        return CatalogCommandError(str(exc), returncode=2)
    if isinstance(exc, CatalogBusyError):
        return CatalogCommandError(str(exc), returncode=3)
    if isinstance(exc, CatalogPackageError):
        code = exc.code
        if code in {
            ErrorCode.STALE_TARGET,
            ErrorCode.PACKAGE_CHANGED,
            ErrorCode.OPERATION_ID_CONFLICT,
            ErrorCode.CATALOG_BUSY,
        }:
            return CatalogCommandError(str(exc), returncode=3)
        if code == ErrorCode.OPERATION_NOT_ALLOWED:
            return CatalogCommandError(str(exc), returncode=4)
        if code in {
            ErrorCode.MEDIA_UNAVAILABLE,
            ErrorCode.IMPORT_FAILED,
            ErrorCode.OUTCOME_UNKNOWN,
        }:
            return CatalogCommandError(str(exc), returncode=5)
        return CatalogCommandError(str(exc), returncode=2)
    return CatalogCommandError("catalog operator operation failed", returncode=5)


def run_command(operation: Callable[[], Any]) -> Any:
    try:
        return operation()
    except Exception as exc:
        raise command_error_for(exc) from exc
