"""Allowlisted append-only Organization audit events."""

from uuid import UUID, uuid4

from django.db import transaction

from .models import OrganizationAuditEvent


ALLOWED_AUDIT_ACTIONS = frozenset(
    {
        "organization.membership.created",
        "organization.membership.updated",
        "organization.membership.revoked",
        "organization.settings.updated",
        "product_commerce.configuration.updated",
    }
)
ALLOWED_AUDIT_TARGET_TYPES = frozenset(
    {
        "organization_membership",
        "organization_settings",
        "product_commerce_configuration",
    }
)
_FORBIDDEN_STATE_KEY_PARTS = frozenset(
    {
        "auth",
        "card",
        "credential",
        "cvv",
        "password",
        "payment",
        "pin",
        "secret",
        "session",
        "token",
    }
)


def _assert_safe_state(value):
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).casefold().replace("-", "_")
            if any(part in normalized.split("_") for part in _FORBIDDEN_STATE_KEY_PARTS):
                raise ValueError("Audit state contains a credential-like key.")
            _assert_safe_state(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _assert_safe_state(child)


def append_audit_event(
    *,
    organization,
    actor,
    action,
    target_type,
    target_identifier,
    before_state=None,
    after_state=None,
    reason="",
    operation_id=None,
):
    """Append one successful event inside the caller's transaction."""
    if transaction.get_autocommit():
        raise RuntimeError("Audit events require the caller's surrounding transaction.")
    if action not in ALLOWED_AUDIT_ACTIONS:
        raise ValueError("Unsupported audit action.")
    if target_type not in ALLOWED_AUDIT_TARGET_TYPES:
        raise ValueError("Unsupported audit target type.")
    if not isinstance(target_identifier, str) or not target_identifier.strip():
        raise ValueError("Audit target identifier is required.")
    if len(target_identifier) > 255:
        raise ValueError("Audit target identifier is too long.")
    if not isinstance(reason, str) or len(reason) > 255:
        raise ValueError("Audit reason is invalid.")
    before_state = {} if before_state is None else before_state
    after_state = {} if after_state is None else after_state
    if not isinstance(before_state, dict) or not isinstance(after_state, dict):
        raise ValueError("Audit state must be an object.")
    _assert_safe_state(before_state)
    _assert_safe_state(after_state)
    if operation_id is None:
        operation_id = uuid4()
    if not isinstance(operation_id, UUID):
        raise ValueError("operation_id must be a UUID.")
    return OrganizationAuditEvent.objects.create(
        organization=organization,
        actor=actor,
        operation_id=operation_id,
        action=action,
        target_type=target_type,
        target_identifier=target_identifier,
        outcome=OrganizationAuditEvent.OUTCOME_SUCCEEDED,
        before_state=before_state,
        after_state=after_state,
        reason=reason,
    )
