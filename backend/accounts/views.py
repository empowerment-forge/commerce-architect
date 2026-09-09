import logging

from django.conf import settings
from django.contrib.auth import authenticate
from django.db import IntegrityError
from rest_framework import permissions, status
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken, TokenError

from .models import AccountProfile, EmailVerification
from .serializers import (
    AccountIdentitySerializer,
    ChangeEmailSerializer,
    PasswordChangeSerializer,
    PasswordRecoveryConfirmSerializer,
    PasswordRecoveryRequestSerializer,
    RegisterSerializer,
    ResendVerificationSerializer,
    SessionTokenObtainPairSerializer,
    SessionTokenRefreshSerializer,
    VerifyEmailSerializer,
)
from .services import (
    InvalidCurrentPassword,
    change_password_and_revoke_sessions,
    change_email,
    consume_password_recovery,
    is_verified,
    normalize_email,
    release_failed_password_recovery_delivery,
    request_password_recovery,
    resend_verification,
    resolve_login_user,
    send_verification_email,
    send_password_recovery_email,
    verification_metadata,
    verify_email,
)


REFRESH_COOKIE_NAME = "refresh_token"
DELIVERY_ERROR = {
    "code": "verification_delivery_failed",
    "detail": "The account is unverified and the email could not be sent. Try resending.",
}
RESEND_DETAIL = (
    "If an eligible unverified account exists and the resend cooldown has elapsed, "
    "a verification email will be sent."
)
PASSWORD_RECOVERY_DETAIL = (
    "If an eligible account exists, password recovery instructions will be sent."
)
logger = logging.getLogger(__name__)


def set_refresh_cookie(response, refresh_token):
    refresh_lifetime = settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=int(refresh_lifetime.total_seconds()),
        httponly=settings.REFRESH_COOKIE_HTTPONLY,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        path=settings.REFRESH_COOKIE_PATH,
    )


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = serializer.save()
        except IntegrityError:
            errors = {}
            if User.objects.filter(
                username=serializer.validated_data["username"]
            ).exists():
                errors["username"] = ["A user with that username already exists."]
            if EmailVerification.objects.filter(
                normalized_email=serializer.validated_data["email"]
            ).exists():
                errors["email"] = ["A user with that email already exists."]
            return Response(
                errors or {"detail": "Username or email is already registered."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            send_verification_email(serializer.issued_verification)
        except (ValueError, OSError):
            return Response(DELIVERY_ERROR, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response(
            {
                "id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone": getattr(
                    getattr(user, "account_profile", None), "phone", ""
                ),
                "email": user.email,
                "email_verified": False,
                "detail": "Registration succeeded. Check your email to verify the account.",
            },
            status=status.HTTP_201_CREATED,
        )


class VerifyEmailView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        verification, result = verify_email(**serializer.validated_data)
        if verification is None:
            return Response(
                {
                    "code": "invalid_or_expired_token",
                    "detail": "The verification link is invalid or expired.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "code": result,
                "detail": (
                    "Email address verified."
                    if result == "verified"
                    else "This email address is already verified."
                ),
                "email": verification.normalized_email,
                "email_verified": True,
                "verified_at": verification.verified_at,
            }
        )


class ResendVerificationView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ResendVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        normalized_email = serializer.validated_data["email"]
        result = resend_verification(normalized_email)
        if result.issued:
            try:
                send_verification_email(result.issued)
            except (ValueError, OSError):
                pass

        return Response({"detail": RESEND_DETAIL}, status=status.HTTP_202_ACCEPTED)


class AuthenticatedResendVerificationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        result = resend_verification(normalize_email(request.user.email))
        if result.status == "cooldown":
            return Response(
                {
                    "code": "resend_cooldown",
                    "detail": (
                        "A verification email was sent recently. "
                        f"Try again in {result.retry_after_seconds} seconds."
                    ),
                    "retry_after_seconds": result.retry_after_seconds,
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        if result.status == "verified":
            return Response(
                {
                    "code": "email_already_verified",
                    "detail": "The current email address is already verified.",
                },
                status=status.HTTP_409_CONFLICT,
            )
        if result.status in {"not_found", "email_mismatch"}:
            return Response(
                {
                    "code": "verification_state_unavailable",
                    "detail": "Verification is unavailable for the current email address.",
                },
                status=status.HTTP_409_CONFLICT,
            )
        if result.issued:
            try:
                send_verification_email(result.issued)
            except (ValueError, OSError):
                return Response(
                    DELIVERY_ERROR,
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

        return Response(
            {
                "code": "verification_email_sent",
                "detail": "Verification email sent to your current email address.",
            },
            status=status.HTTP_202_ACCEPTED,
        )


class TokenObtainCookieView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if settings.AUTH_REQUIRE_VERIFIED_EMAIL:
            resolved_user = resolve_login_user(request.data.get("username"))
            user = None
            if resolved_user is not None:
                user = authenticate(
                    request=request,
                    username=resolved_user.username,
                    password=request.data.get("password"),
                )
            if user is not None and not is_verified(user):
                return Response(
                    {
                        "code": "email_not_verified",
                        "detail": "Verify your current email address before logging in.",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        serializer = SessionTokenObtainPairSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        response = Response(
            {"access": serializer.validated_data["access"]},
            status=status.HTTP_200_OK,
        )
        set_refresh_cookie(response, serializer.validated_data["refresh"])
        return response


class TokenRefreshCookieView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        refresh_cookie = request.COOKIES.get(REFRESH_COOKIE_NAME)
        if not refresh_cookie:
            raise AuthenticationFailed("Refresh token cookie is missing.")

        serializer = SessionTokenRefreshSerializer(data={"refresh": refresh_cookie})
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            raise AuthenticationFailed("Refresh token is invalid.") from exc

        response = Response(
            {"access": serializer.validated_data["access"]},
            status=status.HTTP_200_OK,
        )
        new_refresh = serializer.validated_data.get("refresh")
        if new_refresh:
            set_refresh_cookie(response, new_refresh)
        return response


class LogoutView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        refresh_cookie = request.COOKIES.get(REFRESH_COOKIE_NAME)
        if refresh_cookie:
            try:
                RefreshToken(refresh_cookie).blacklist()
            except TokenError:
                pass

        response = Response({"detail": "Logged out."}, status=status.HTTP_200_OK)
        response.delete_cookie(
            key=REFRESH_COOKIE_NAME,
            path=settings.REFRESH_COOKIE_PATH,
            samesite=settings.REFRESH_COOKIE_SAMESITE,
        )
        return response


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        email_verified, verified_at = verification_metadata(request.user)
        phone = (
            AccountProfile.objects.filter(user=request.user)
            .values_list("phone", flat=True)
            .first()
            or ""
        )
        return Response(
            {
                "id": request.user.id,
                "username": request.user.username,
                "first_name": request.user.first_name,
                "last_name": request.user.last_name,
                "phone": phone,
                "email": request.user.email,
                "email_verified": email_verified,
                "email_verified_at": verified_at,
            },
            status=status.HTTP_200_OK,
        )

    def patch(self, request):
        serializer = AccountIdentitySerializer(
            request.user,
            data=request.data,
            partial=False,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        phone = (
            AccountProfile.objects.filter(user=user)
            .values_list("phone", flat=True)
            .first()
            or ""
        )
        return Response(
            {
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone": phone,
                "detail": "Personal information updated.",
            }
        )


class PasswordChangeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        try:
            change_password_and_revoke_sessions(
                request.user.pk,
                serializer.validated_data["current_password"],
                serializer.validated_data["new_password"],
            )
        except InvalidCurrentPassword:
            return Response(
                {"current_password": ["Current password is incorrect."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        response = Response(
            {
                "code": "password_changed",
                "detail": "Password changed successfully. Please sign in again.",
            }
        )
        response.delete_cookie(
            key=REFRESH_COOKIE_NAME,
            path=settings.REFRESH_COOKIE_PATH,
            samesite=settings.REFRESH_COOKIE_SAMESITE,
        )
        return response


class ChangeEmailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangeEmailSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        try:
            issued = change_email(request.user, serializer.validated_data["email"])
        except IntegrityError:
            return Response(
                {"email": ["A user with that email already exists."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            send_verification_email(issued)
        except (ValueError, OSError):
            return Response(
                {
                    **DELIVERY_ERROR,
                    "email": issued.verification.normalized_email,
                    "email_verified": False,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "email": issued.verification.normalized_email,
                "email_verified": False,
                "detail": "Email changed. Check the new address to verify it.",
            }
        )


class PasswordRecoveryRequestView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_recovery_request"

    def post(self, request):
        serializer = PasswordRecoveryRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = request_password_recovery(serializer.validated_data["email"])
        if result.issued:
            try:
                send_password_recovery_email(result.issued)
            except Exception:  # Mail backends may raise provider-specific exceptions.
                logger.warning("Password recovery email delivery failed.")
                release_failed_password_recovery_delivery(result.issued)
        return Response(
            {"detail": PASSWORD_RECOVERY_DETAIL},
            status=status.HTTP_202_ACCEPTED,
        )


class PasswordRecoveryConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordRecoveryConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            if "code" in serializer.errors:
                return Response(
                    {
                        "code": "invalid_or_expired_token",
                        "detail": "This password reset link is invalid or expired.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            raise ValidationError(serializer.errors)
        if not consume_password_recovery(
            serializer.validated_data["uid"],
            serializer.validated_data["token"],
            serializer.validated_data["new_password"],
        ):
            return Response(
                {
                    "code": "invalid_or_expired_token",
                    "detail": "This password reset link is invalid or expired.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        response = Response(
            {
                "code": "password_reset",
                "detail": "Password changed. Please log in.",
            }
        )
        response.delete_cookie(
            key=REFRESH_COOKIE_NAME,
            path=settings.REFRESH_COOKIE_PATH,
            samesite=settings.REFRESH_COOKIE_SAMESITE,
        )
        return response
