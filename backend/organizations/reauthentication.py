"""Session-bound, short-lived recent password authentication proofs."""

import secrets

from django.conf import settings
from django.core import signing
from django.utils import timezone

from accounts.models import AccountSecurityState

RECENT_AUTHENTICATION_SALT = "commerce-architect.operator-recent-authentication.v1"
RECENT_AUTHENTICATION_PURPOSE = "product_commerce.configuration"


def _auth_value(request, key):
    auth = getattr(request, "auth", None)
    return auth.get(key) if hasattr(auth, "get") else None


def _session_id(request):
    value = _auth_value(request, "session_id")
    if not isinstance(value, str) or not value:
        raise ValueError("A current token-family session_id is required.")
    return value


def issue_recent_authentication(*, request, organization_id, purpose):
    session_id = _session_id(request)
    generation = _auth_value(request, "session_generation")
    if isinstance(generation, bool) or not isinstance(generation, int) or generation < 0:
        raise ValueError("A valid current security generation is required.")
    payload = {
        "user_id": str(request.user.pk),
        "session_id": session_id,
        "session_generation": generation,
        "organization_id": int(organization_id),
        "purpose": purpose,
        "issued_at": int(timezone.now().timestamp()),
        "nonce": secrets.token_urlsafe(32),
    }
    return signing.dumps(payload, salt=RECENT_AUTHENTICATION_SALT, compress=True)


def verify_recent_authentication(*, request, organization_id, purpose, proof):
    if not isinstance(proof, str) or not proof:
        return False
    try:
        payload = signing.loads(
            proof,
            salt=RECENT_AUTHENTICATION_SALT,
            max_age=settings.OPERATOR_RECENT_AUTHENTICATION_SECONDS,
        )
    except signing.BadSignature:
        return False
    try:
        current_generation = (
            AccountSecurityState.objects.filter(user_id=request.user.pk)
            .values_list("session_generation", flat=True)
            .first()
        )
        if current_generation is None:
            current_generation = 0
        return (
            payload.get("user_id") == str(request.user.pk)
            and payload.get("session_id") == _session_id(request)
            and payload.get("session_generation") == _auth_value(request, "session_generation")
            and payload.get("session_generation") == current_generation
            and payload.get("organization_id") == int(organization_id)
            and payload.get("purpose") == purpose
            and isinstance(payload.get("issued_at"), int)
            and isinstance(payload.get("nonce"), str)
            and bool(payload["nonce"])
        )
    except (TypeError, ValueError, KeyError):
        return False
