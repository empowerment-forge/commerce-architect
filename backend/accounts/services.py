import hashlib
import math
import secrets
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import EmailVerification


def normalize_email(value):
    return value.strip().casefold()


def token_digest(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class IssuedVerification:
    verification: EmailVerification
    token: str


@dataclass(frozen=True)
class ResendVerificationResult:
    status: str
    issued: IssuedVerification | None = None
    retry_after_seconds: int | None = None


def issue_verification(verification):
    token = secrets.token_urlsafe(32)
    now = timezone.now()
    verification.token_digest = token_digest(token)
    verification.token_created_at = now
    verification.last_sent_at = now
    verification.save(
        update_fields=["token_digest", "token_created_at", "last_sent_at", "updated_at"]
    )
    return IssuedVerification(verification=verification, token=token)


@transaction.atomic
def resend_verification(normalized_email):
    try:
        verification = (
            EmailVerification.objects.select_for_update()
            .select_related("user")
            .get(normalized_email=normalized_email)
        )
    except EmailVerification.DoesNotExist:
        return ResendVerificationResult(status="not_found")

    cooldown = timedelta(
        seconds=settings.AUTH_EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS
    )
    current_email = normalize_email(verification.user.email)
    if is_verified(verification.user):
        return ResendVerificationResult(status="verified")
    if current_email != verification.normalized_email:
        return ResendVerificationResult(status="email_mismatch")
    now = timezone.now()
    if (
        verification.last_sent_at is not None
        and now < verification.last_sent_at + cooldown
    ):
        retry_after = math.ceil(
            (verification.last_sent_at + cooldown - now).total_seconds()
        )
        return ResendVerificationResult(
            status="cooldown",
            retry_after_seconds=max(1, retry_after),
        )
    return ResendVerificationResult(
        status="sent",
        issued=issue_verification(verification),
    )


def verification_url(issued):
    query = urlencode({"uid": str(issued.verification.pk), "token": issued.token})
    return f"{settings.AUTH_FRONTEND_BASE_URL}/verify-email?{query}"


def send_verification_email(issued):
    send_mail(
        subject="Verify your Commerce Architect email",
        message=(
            "Verify your email address by opening this link:\n\n"
            f"{verification_url(issued)}\n\n"
            "If you did not request this, you can ignore this message."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[issued.verification.normalized_email],
        fail_silently=False,
    )


def is_verified(user):
    try:
        verification = user.email_verification
    except EmailVerification.DoesNotExist:
        return False
    return bool(
        verification.verified_at
        and verification.normalized_email == normalize_email(user.email)
    )


def verification_metadata(user):
    try:
        verification = user.email_verification
    except EmailVerification.DoesNotExist:
        return False, None
    verified = is_verified(user)
    return verified, verification.verified_at if verified else None


@transaction.atomic
def verify_email(uid, token):
    try:
        verification = (
            EmailVerification.objects.select_for_update()
            .select_related("user")
            .get(pk=uid)
        )
    except (EmailVerification.DoesNotExist, ValueError):
        return None, "invalid_or_expired_token"

    current_email = normalize_email(verification.user.email)
    if verification.normalized_email != current_email:
        return None, "invalid_or_expired_token"

    candidate_digest = token_digest(token)
    if not verification.token_digest or not secrets.compare_digest(
        verification.token_digest,
        candidate_digest,
    ):
        return None, "invalid_or_expired_token"

    if verification.verified_at:
        return verification, "already_verified"

    expires_at = verification.token_created_at + timedelta(
        seconds=settings.AUTH_EMAIL_VERIFICATION_TTL_SECONDS
    )
    if timezone.now() > expires_at:
        return None, "invalid_or_expired_token"

    verification.verified_at = timezone.now()
    verification.save(update_fields=["verified_at", "updated_at"])
    return verification, "verified"


@transaction.atomic
def change_email(user, normalized_email):
    verification, _ = EmailVerification.objects.select_for_update().get_or_create(
        user=user,
        defaults={"normalized_email": normalized_email},
    )
    user.email = normalized_email
    user.save(update_fields=["email"])
    verification.normalized_email = normalized_email
    verification.verified_at = None
    verification.token_digest = ""
    verification.token_created_at = None
    verification.save(
        update_fields=[
            "normalized_email",
            "verified_at",
            "token_digest",
            "token_created_at",
            "updated_at",
        ]
    )
    return issue_verification(verification)
