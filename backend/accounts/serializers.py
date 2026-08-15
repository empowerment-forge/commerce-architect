from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
)
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken

from .models import AccountSecurityState, EmailVerification
from .services import get_valid_password_recovery, issue_verification, normalize_email


class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=True, allow_blank=False)
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "password"]

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("A user with that username already exists.")
        return value

    def validate_email(self, value):
        normalized = normalize_email(value)
        if EmailVerification.objects.filter(normalized_email=normalized).exists():
            raise serializers.ValidationError("A user with that email already exists.")
        return normalized

    def validate(self, attrs):
        prospective_user = User(username=attrs.get("username"), email=attrs.get("email"))
        try:
            validate_password(attrs.get("password"), user=prospective_user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        verification = EmailVerification.objects.create(
            user=user,
            normalized_email=user.email,
        )
        self.issued_verification = issue_verification(verification)
        return user


class VerifyEmailSerializer(serializers.Serializer):
    uid = serializers.UUIDField()
    token = serializers.CharField(trim_whitespace=False, allow_blank=False)


class ResendVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True, allow_blank=False)

    def validate_email(self, value):
        return normalize_email(value)


class ChangeEmailSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True, allow_blank=False)

    def validate_email(self, value):
        normalized = normalize_email(value)
        user = self.context["request"].user
        if EmailVerification.objects.exclude(user=user).filter(
            normalized_email=normalized
        ).exists():
            raise serializers.ValidationError("A user with that email already exists.")
        if normalize_email(user.email) == normalized:
            raise serializers.ValidationError("Enter a different email address.")
        return normalized


class PasswordRecoveryRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True, allow_blank=False)

    def validate_email(self, value):
        return normalize_email(value)


class PasswordRecoveryConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField(trim_whitespace=False, allow_blank=False)
    token = serializers.CharField(trim_whitespace=False, allow_blank=False)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)
    confirm_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": ["Passwords do not match."]}
            )
        recovery = get_valid_password_recovery(attrs["uid"], attrs["token"])
        if recovery is None:
            raise serializers.ValidationError(
                {
                    "code": "invalid_or_expired_token",
                    "detail": "This password reset link is invalid or expired.",
                }
            )
        try:
            validate_password(attrs["new_password"], user=recovery.user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                {"new_password": list(exc.messages)}
            ) from exc
        attrs["recovery"] = recovery
        return attrs


class SessionTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        security, _ = AccountSecurityState.objects.get_or_create(user=user)
        token["session_generation"] = security.session_generation
        return token


class SessionTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        refresh = RefreshToken(attrs["refresh"])
        user_id = refresh.get(api_settings.USER_ID_CLAIM)
        generation = (
            AccountSecurityState.objects.filter(user_id=user_id)
            .values_list("session_generation", flat=True)
            .first()
            or 0
        )
        if refresh.get("session_generation", 0) != generation:
            raise InvalidToken("Refresh session has been revoked.")
        return super().validate(attrs)
