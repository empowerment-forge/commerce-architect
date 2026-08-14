from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from .models import EmailVerification
from .services import issue_verification, normalize_email


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
