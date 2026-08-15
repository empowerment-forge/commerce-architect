import hashlib
import hmac
import math
import secrets
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)

from .models import AccountSecurityState, EmailVerification, PasswordRecoveryState


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


@dataclass(frozen=True)
class IssuedPasswordRecovery:
    recovery: PasswordRecoveryState
    token: str
    previous_last_sent_at: object


@dataclass(frozen=True)
class PasswordRecoveryRequestResult:
    status: str
    issued: IssuedPasswordRecovery | None = None


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


def password_recovery_digest(token, user, normalized_email):
    message = "\0".join(
        (token, str(user.pk), user.password, normalized_email)
    ).encode("utf-8")
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"), message, hashlib.sha256
    ).hexdigest()


@transaction.atomic
def request_password_recovery(normalized_email):
    try:
        verification = (
            EmailVerification.objects.select_for_update()
            .select_related("user")
            .get(normalized_email=normalized_email)
        )
    except EmailVerification.DoesNotExist:
        return PasswordRecoveryRequestResult(status="ineligible")

    user = verification.user
    if (
        not user.is_active
        or not is_verified(user)
        or normalize_email(user.email) != normalized_email
        or verification.normalized_email != normalized_email
    ):
        return PasswordRecoveryRequestResult(status="ineligible")

    recovery, _ = PasswordRecoveryState.objects.select_for_update().get_or_create(
        user=user,
        defaults={"normalized_email": normalized_email},
    )
    now = timezone.now()
    cooldown = timedelta(
        seconds=settings.AUTH_PASSWORD_RECOVERY_RESEND_COOLDOWN_SECONDS
    )
    if recovery.last_sent_at and now < recovery.last_sent_at + cooldown:
        return PasswordRecoveryRequestResult(status="cooldown")

    previous_last_sent_at = recovery.last_sent_at
    token = secrets.token_urlsafe(32)
    recovery.normalized_email = normalized_email
    recovery.token_digest = password_recovery_digest(token, user, normalized_email)
    recovery.token_created_at = now
    recovery.last_sent_at = now
    recovery.consumed_at = None
    recovery.save(
        update_fields=[
            "normalized_email",
            "token_digest",
            "token_created_at",
            "last_sent_at",
            "consumed_at",
            "updated_at",
        ]
    )
    return PasswordRecoveryRequestResult(
        status="issued",
        issued=IssuedPasswordRecovery(recovery, token, previous_last_sent_at),
    )


def password_recovery_url(issued):
    query = urlencode({"uid": str(issued.recovery.pk), "token": issued.token})
    return f"{settings.AUTH_FRONTEND_BASE_URL}/reset-password?{query}"


def send_password_recovery_email(issued):
    send_mail(
        subject="Reset your Commerce Architect password",
        message=(
            "Reset your password by opening this link:\n\n"
            f"{password_recovery_url(issued)}\n\n"
            "If you did not request this, you can ignore this message."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[issued.recovery.normalized_email],
        fail_silently=False,
    )


@transaction.atomic
def release_failed_password_recovery_delivery(issued):
    recovery = PasswordRecoveryState.objects.select_for_update().select_related(
        "user"
    ).get(pk=issued.recovery.pk)
    expected_digest = password_recovery_digest(
        issued.token, recovery.user, recovery.normalized_email
    )
    if not secrets.compare_digest(recovery.token_digest, expected_digest):
        return
    recovery.token_digest = ""
    recovery.token_created_at = None
    recovery.last_sent_at = issued.previous_last_sent_at
    recovery.save(
        update_fields=[
            "token_digest",
            "token_created_at",
            "last_sent_at",
            "updated_at",
        ]
    )


def _valid_password_recovery(recovery, token, now=None):
    now = now or timezone.now()
    user = recovery.user
    try:
        verification = user.email_verification
    except EmailVerification.DoesNotExist:
        return False
    current_email = normalize_email(user.email)
    if (
        not recovery.token_digest
        or recovery.token_created_at is None
        or recovery.consumed_at is not None
        or not user.is_active
        or not verification.verified_at
        or recovery.normalized_email != current_email
        or verification.normalized_email != current_email
    ):
        return False
    expires_at = recovery.token_created_at + timedelta(
        seconds=settings.AUTH_PASSWORD_RECOVERY_TTL_SECONDS
    )
    if now > expires_at:
        return False
    expected = password_recovery_digest(token, user, recovery.normalized_email)
    return secrets.compare_digest(recovery.token_digest, expected)


def get_valid_password_recovery(uid, token):
    try:
        recovery = PasswordRecoveryState.objects.select_related(
            "user", "user__email_verification"
        ).get(pk=uid)
    except (PasswordRecoveryState.DoesNotExist, ValueError):
        return None
    return recovery if _valid_password_recovery(recovery, token) else None


@transaction.atomic
def consume_password_recovery(uid, token, new_password):
    try:
        recovery = (
            PasswordRecoveryState.objects.select_for_update()
            .select_related("user")
            .get(pk=uid)
        )
    except (PasswordRecoveryState.DoesNotExist, ValueError):
        return False
    if not _valid_password_recovery(recovery, token):
        return False

    user = User.objects.select_for_update().get(pk=recovery.user_id)
    security, _ = AccountSecurityState.objects.select_for_update().get_or_create(
        user=user
    )
    user.set_password(new_password)
    user.save(update_fields=["password"])
    recovery.token_digest = ""
    recovery.consumed_at = timezone.now()
    recovery.save(update_fields=["token_digest", "consumed_at", "updated_at"])
    security.session_generation += 1
    security.save(update_fields=["session_generation", "updated_at"])

    outstanding = OutstandingToken.objects.filter(user=user).only("id")
    BlacklistedToken.objects.bulk_create(
        [BlacklistedToken(token=item) for item in outstanding],
        ignore_conflicts=True,
    )
    return True


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
    PasswordRecoveryState.objects.filter(user=user).update(
        token_digest="",
        token_created_at=None,
        consumed_at=None,
        updated_at=timezone.now(),
    )
    return issue_verification(verification)
