import secrets

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

from .models import AccountProfile, AccountSecurityState, EmailVerification
from .services import (
    get_valid_password_recovery,
    issue_verification,
    normalize_email,
    resolve_login_user,
)
from .validators import normalize_and_validate_phone


class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=True, allow_blank=False)
    first_name = serializers.CharField(required=True, allow_blank=False, max_length=150)
    last_name = serializers.CharField(required=True, allow_blank=False, max_length=150)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=32)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "phone",
            "email",
            "password",
        ]

    def validate_first_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("First name is required.")
        return value

    def validate_last_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Last name is required.")
        return value

    def validate_phone(self, value):
        try:
            return normalize_and_validate_phone(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("A user with that username already exists.")
        if EmailVerification.objects.filter(
            normalized_email=normalize_email(value)
        ).exists():
            raise serializers.ValidationError(
                "This username conflicts with an existing account identity."
            )
        return value

    def validate_email(self, value):
        normalized = normalize_email(value)
        if EmailVerification.objects.filter(normalized_email=normalized).exists():
            raise serializers.ValidationError("A user with that email already exists.")
        if User.objects.filter(username__iexact=normalized).exists():
            raise serializers.ValidationError(
                "This email conflicts with an existing account identity."
            )
        return normalized

    def validate(self, attrs):
        prospective_user = User(
            username=attrs.get("username"),
            email=attrs.get("email"),
            first_name=attrs.get("first_name"),
            last_name=attrs.get("last_name"),
        )
        try:
            validate_password(attrs.get("password"), user=prospective_user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        phone = validated_data.pop("phone", "")
        user = User.objects.create_user(**validated_data)
        if phone:
            AccountProfile.objects.create(user=user, phone=phone)
        verification = EmailVerification.objects.create(
            user=user,
            normalized_email=user.email,
        )
        self.issued_verification = issue_verification(verification)
        return user


class AccountIdentitySerializer(serializers.Serializer):
    first_name = serializers.CharField(required=True, allow_blank=False, max_length=150)
    last_name = serializers.CharField(required=True, allow_blank=False, max_length=150)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=32)

    def validate_first_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("First name is required.")
        return value

    def validate_last_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Last name is required.")
        return value

    def validate_phone(self, value):
        try:
            return normalize_and_validate_phone(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc

    @transaction.atomic
    def update(self, instance, validated_data):
        user = User.objects.select_for_update().get(pk=instance.pk)
        user.first_name = validated_data["first_name"]
        user.last_name = validated_data["last_name"]
        user.save(update_fields=["first_name", "last_name"])
        phone = validated_data.get("phone", "")
        if phone:
            profile, _ = AccountProfile.objects.select_for_update().get_or_create(
                user=user
            )
            profile.phone = phone
            profile.save(update_fields=["phone", "updated_at"])
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
        if User.objects.exclude(pk=user.pk).filter(username__iexact=normalized).exists():
            raise serializers.ValidationError(
                "This email conflicts with an existing account identity."
            )
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
    def validate(self, attrs):
        user = resolve_login_user(attrs.get(self.username_field))
        credentials = dict(attrs)
        credentials[self.username_field] = (
            user.username if user is not None else "__invalid_login_identifier__"
        )
        return super().validate(credentials)

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        security, _ = AccountSecurityState.objects.get_or_create(user=user)
        token["session_generation"] = security.session_generation
        token["session_id"] = secrets.token_urlsafe(32)
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


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password_confirmation = serializers.CharField(
        write_only=True, trim_whitespace=False
    )

    def validate_current_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirmation"]:
            raise serializers.ValidationError(
                {"new_password_confirmation": ["Passwords do not match."]}
            )
        try:
            validate_password(
                attrs["new_password"], user=self.context["request"].user
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                {"new_password": list(exc.messages)}
            ) from exc
        return attrs


class ReauthenticationSerializer(serializers.Serializer):
    organization_id = serializers.IntegerField(min_value=1)
    purpose = serializers.CharField(max_length=64, allow_blank=False)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
