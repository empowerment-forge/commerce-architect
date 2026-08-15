import json
import os
import subprocess
import sys


SECURITY_ENV_NAMES = (
    "COMMERCE_ENV",
    "DJANGO_SECRET_KEY",
    "DJANGO_DEBUG",
    "DJANGO_ALLOWED_HOSTS",
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "DJANGO_SECURE_SSL_REDIRECT",
    "DJANGO_SECURE_HSTS_SECONDS",
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS",
    "DJANGO_SECURE_HSTS_PRELOAD",
    "DJANGO_TRUST_FORWARDED_PROTO",
    "AUTH_REQUIRE_VERIFIED_EMAIL",
    "AUTH_EMAIL_VERIFICATION_TTL_SECONDS",
    "AUTH_EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS",
    "AUTH_PASSWORD_RECOVERY_TTL_SECONDS",
    "AUTH_PASSWORD_RECOVERY_RESEND_COOLDOWN_SECONDS",
    "AUTH_FRONTEND_BASE_URL",
    "EMAIL_BACKEND",
    "DEFAULT_FROM_EMAIL",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "SMTP_USE_TLS",
    "SMTP_USE_SSL",
    "SMTP_TIMEOUT",
    "DATABASE_HOST",
    "DATABASE_NAME",
    "DATABASE_USER",
    "DATABASE_PASSWORD",
    "DATABASE_PORT",
)

SETTINGS_PROBE = """
import json
from django.conf import settings

print(json.dumps({
    "environment": settings.COMMERCE_ENV,
    "debug": settings.DEBUG,
    "allowed_hosts": settings.ALLOWED_HOSTS,
    "csrf_trusted_origins": settings.CSRF_TRUSTED_ORIGINS,
    "session_cookie_secure": settings.SESSION_COOKIE_SECURE,
    "csrf_cookie_secure": settings.CSRF_COOKIE_SECURE,
    "refresh_cookie_secure": settings.REFRESH_COOKIE_SECURE,
    "refresh_cookie_httponly": settings.REFRESH_COOKIE_HTTPONLY,
    "refresh_cookie_samesite": settings.REFRESH_COOKIE_SAMESITE,
    "refresh_cookie_path": settings.REFRESH_COOKIE_PATH,
    "ssl_redirect": settings.SECURE_SSL_REDIRECT,
    "hsts_seconds": settings.SECURE_HSTS_SECONDS,
    "proxy_ssl_header": getattr(settings, "SECURE_PROXY_SSL_HEADER", None),
    "require_verified_email": settings.AUTH_REQUIRE_VERIFIED_EMAIL,
    "verification_ttl": settings.AUTH_EMAIL_VERIFICATION_TTL_SECONDS,
    "resend_cooldown": settings.AUTH_EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS,
    "password_recovery_ttl": settings.AUTH_PASSWORD_RECOVERY_TTL_SECONDS,
    "password_recovery_cooldown": settings.AUTH_PASSWORD_RECOVERY_RESEND_COOLDOWN_SECONDS,
    "api_num_proxies": settings.REST_FRAMEWORK["NUM_PROXIES"],
    "auth_frontend_base_url": settings.AUTH_FRONTEND_BASE_URL,
    "email_backend": settings.MAILERS["default"]["BACKEND"],
    "mailer_options": {
        key: ("configured" if key == "password" else value)
        for key, value in settings.MAILERS["default"].get("OPTIONS", {}).items()
    },
    "default_from_email": settings.DEFAULT_FROM_EMAIL,
}))
"""

SMTP_ENV = {
    "SMTP_HOST": "smtp.example.com",
    "SMTP_PORT": "587",
    "SMTP_USERNAME": "smtp-user",
    "SMTP_PASSWORD": "smtp-test-password",
    "SMTP_USE_TLS": "true",
    "SMTP_USE_SSL": "false",
    "SMTP_TIMEOUT": "15",
}


def run_settings_probe(**overrides):
    environment = os.environ.copy()
    for name in SECURITY_ENV_NAMES:
        environment.pop(name, None)
    environment.update(overrides)
    environment["DJANGO_SETTINGS_MODULE"] = "config.settings"
    return subprocess.run(
        [sys.executable, "-c", SETTINGS_PROBE],
        capture_output=True,
        check=False,
        env=environment,
        text=True,
    )


def test_environment_must_be_explicitly_selected():
    result = run_settings_probe(
        DJANGO_SECRET_KEY="django-insecure-development-only-not-for-production",
    )

    assert result.returncode != 0
    assert "COMMERCE_ENV must be explicitly set" in result.stderr


def test_development_loads_with_explicit_safe_environment():
    result = run_settings_probe(
        COMMERCE_ENV="development",
        DJANGO_SECRET_KEY="django-insecure-development-only-not-for-production",
    )

    assert result.returncode == 0, result.stderr
    settings = json.loads(result.stdout)
    assert settings["environment"] == "development"
    assert settings["debug"] is True
    assert "localhost" in settings["allowed_hosts"]
    assert settings["session_cookie_secure"] is False
    assert settings["csrf_cookie_secure"] is False
    assert settings["refresh_cookie_secure"] is False
    assert settings["refresh_cookie_httponly"] is True
    assert settings["refresh_cookie_samesite"] == "Strict"
    assert settings["refresh_cookie_path"] == "/api/auth/"
    assert settings["ssl_redirect"] is False
    assert settings["require_verified_email"] is False
    assert settings["verification_ttl"] == 86400
    assert settings["resend_cooldown"] == 60
    assert settings["password_recovery_ttl"] == 1800
    assert settings["password_recovery_cooldown"] == 60
    assert settings["api_num_proxies"] == 0
    assert settings["auth_frontend_base_url"] == "http://localhost:5173"
    assert settings["email_backend"] == "accounts.mail.ReadableConsoleEmailBackend"
    assert settings["mailer_options"] == {}


def test_development_builds_smtp_mailer_options():
    result = run_settings_probe(
        COMMERCE_ENV="development",
        DJANGO_SECRET_KEY="django-insecure-development-only-not-for-production",
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        **SMTP_ENV,
    )

    assert result.returncode == 0, result.stderr
    mailer = json.loads(result.stdout)
    assert mailer["email_backend"] == "django.core.mail.backends.smtp.EmailBackend"
    assert mailer["mailer_options"] == {
        "host": "smtp.example.com",
        "port": 587,
        "username": "smtp-user",
        "password": "configured",
        "use_tls": True,
        "use_ssl": False,
        "timeout": 15,
    }


def test_smtp_requires_credentials_and_valid_connection_options():
    base = {
        "COMMERCE_ENV": "development",
        "DJANGO_SECRET_KEY": "django-insecure-development-only-not-for-production",
        "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
    }

    missing = run_settings_probe(**base)
    assert missing.returncode != 0
    assert "SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD" in missing.stderr

    invalid_port = run_settings_probe(**base, **{**SMTP_ENV, "SMTP_PORT": "70000"})
    assert invalid_port.returncode != 0
    assert "SMTP_PORT must be between 1 and 65535" in invalid_port.stderr

    invalid_timeout = run_settings_probe(**base, **{**SMTP_ENV, "SMTP_TIMEOUT": "0"})
    assert invalid_timeout.returncode != 0
    assert "SMTP_TIMEOUT must be positive" in invalid_timeout.stderr


def test_smtp_tls_and_ssl_are_mutually_exclusive_without_exposing_credentials():
    secret = "credential-must-never-appear"
    result = run_settings_probe(
        COMMERCE_ENV="development",
        DJANGO_SECRET_KEY="django-insecure-development-only-not-for-production",
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        **{
            **SMTP_ENV,
            "SMTP_PASSWORD": secret,
            "SMTP_USE_TLS": "true",
            "SMTP_USE_SSL": "true",
        },
    )

    assert result.returncode != 0
    assert "cannot both be enabled" in result.stderr
    assert secret not in result.stdout
    assert secret not in result.stderr


def test_development_requires_explicit_secret_key():
    result = run_settings_probe(COMMERCE_ENV="development")

    assert result.returncode != 0
    assert "Development requires DJANGO_SECRET_KEY" in result.stderr


def test_production_requires_secret_key():
    result = run_settings_probe(
        COMMERCE_ENV="production",
        DJANGO_ALLOWED_HOSTS="commerce.example",
    )

    assert result.returncode != 0
    assert "Production requires a strong DJANGO_SECRET_KEY" in result.stderr


def test_production_rejects_low_diversity_secret_key():
    result = run_settings_probe(
        COMMERCE_ENV="production",
        DJANGO_SECRET_KEY="a" * 60,
        DJANGO_ALLOWED_HOSTS="commerce.example",
    )

    assert result.returncode != 0
    assert "Production requires a strong DJANGO_SECRET_KEY" in result.stderr


def test_production_rejects_debug_true():
    result = run_settings_probe(
        COMMERCE_ENV="production",
        DJANGO_SECRET_KEY="production-secret-with-more-than-fifty-safe-characters-123456",
        DJANGO_ALLOWED_HOSTS="commerce.example",
        DJANGO_DEBUG="true",
    )

    assert result.returncode != 0
    assert "DJANGO_DEBUG cannot be enabled in production" in result.stderr


def test_production_requires_allowed_hosts():
    result = run_settings_probe(
        COMMERCE_ENV="production",
        DJANGO_SECRET_KEY="production-secret-with-more-than-fifty-safe-characters-123456",
    )

    assert result.returncode != 0
    assert "Production requires DJANGO_ALLOWED_HOSTS" in result.stderr


def test_production_requires_database_configuration():
    result = run_settings_probe(
        COMMERCE_ENV="production",
        DJANGO_SECRET_KEY="production-secret-with-more-than-fifty-safe-characters-123456",
        DJANGO_ALLOWED_HOSTS="commerce.example",
        AUTH_FRONTEND_BASE_URL="https://commerce.example",
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        DEFAULT_FROM_EMAIL="Commerce Architect <noreply@commerce.example>",
        **SMTP_ENV,
    )

    assert result.returncode != 0
    assert "Production requires database configuration" in result.stderr


def test_production_rejects_development_only_hosts():
    result = run_settings_probe(
        COMMERCE_ENV="production",
        DJANGO_SECRET_KEY="production-secret-with-more-than-fifty-safe-characters-123456",
        DJANGO_ALLOWED_HOSTS="localhost,web",
    )

    assert result.returncode != 0
    assert "must include a deployment hostname" in result.stderr


def test_production_rejects_wildcard_allowed_hosts():
    result = run_settings_probe(
        COMMERCE_ENV="production",
        DJANGO_SECRET_KEY="production-secret-with-more-than-fifty-safe-characters-123456",
        DJANGO_ALLOWED_HOSTS="*",
    )

    assert result.returncode != 0
    assert "cannot contain the wildcard '*'" in result.stderr


def test_production_rejects_known_development_database_password():
    result = run_settings_probe(
        COMMERCE_ENV="production",
        DJANGO_SECRET_KEY="production-secret-with-more-than-fifty-safe-characters-123456",
        DJANGO_ALLOWED_HOSTS="commerce.example",
        DATABASE_HOST="database.example",
        DATABASE_NAME="commerce",
        DATABASE_USER="commerce",
        DATABASE_PASSWORD="commercepass",
        AUTH_FRONTEND_BASE_URL="https://commerce.example",
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        DEFAULT_FROM_EMAIL="Commerce Architect <noreply@commerce.example>",
        **SMTP_ENV,
    )

    assert result.returncode != 0
    assert "rejects the known development DATABASE_PASSWORD" in result.stderr


def test_explicit_production_enables_secure_defaults_and_proxy_support():
    result = run_settings_probe(
        COMMERCE_ENV="production",
        DJANGO_SECRET_KEY="production-secret-with-more-than-fifty-safe-characters-123456",
        DJANGO_ALLOWED_HOSTS="commerce.example,api.commerce.example",
        DJANGO_CSRF_TRUSTED_ORIGINS="https://commerce.example",
        DJANGO_TRUST_FORWARDED_PROTO="true",
        DATABASE_HOST="database.example",
        DATABASE_NAME="commerce",
        DATABASE_USER="commerce",
        DATABASE_PASSWORD="not-a-real-production-password",
        AUTH_REQUIRE_VERIFIED_EMAIL="true",
        AUTH_FRONTEND_BASE_URL="https://commerce.example",
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        DEFAULT_FROM_EMAIL="Commerce Architect <noreply@commerce.example>",
        **SMTP_ENV,
    )

    assert result.returncode == 0, result.stderr
    settings = json.loads(result.stdout)
    assert settings["debug"] is False
    assert settings["allowed_hosts"] == [
        "commerce.example",
        "api.commerce.example",
    ]
    assert settings["csrf_trusted_origins"] == ["https://commerce.example"]
    assert settings["session_cookie_secure"] is True
    assert settings["csrf_cookie_secure"] is True
    assert settings["refresh_cookie_secure"] is True
    assert settings["refresh_cookie_httponly"] is True
    assert settings["refresh_cookie_samesite"] == "Strict"
    assert settings["refresh_cookie_path"] == "/api/auth/"
    assert settings["ssl_redirect"] is True
    assert settings["hsts_seconds"] == 0
    assert settings["proxy_ssl_header"] == ["HTTP_X_FORWARDED_PROTO", "https"]
    assert settings["api_num_proxies"] == 1
    assert settings["require_verified_email"] is True
    assert settings["auth_frontend_base_url"] == "https://commerce.example"


def test_production_rejects_unsafe_auth_email_configuration():
    base = {
        "COMMERCE_ENV": "production",
        "DJANGO_SECRET_KEY": "production-secret-with-more-than-fifty-safe-characters-123456",
        "DJANGO_ALLOWED_HOSTS": "commerce.example",
        "DATABASE_HOST": "database.example",
        "DATABASE_NAME": "commerce",
        "DATABASE_USER": "commerce",
        "DATABASE_PASSWORD": "not-a-real-production-password",
        "DEFAULT_FROM_EMAIL": "Commerce Architect <noreply@commerce.example>",
        **SMTP_ENV,
    }

    missing_url = run_settings_probe(
        **base,
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
    )
    assert missing_url.returncode != 0
    assert "AUTH_FRONTEND_BASE_URL" in missing_url.stderr

    console_backend = run_settings_probe(
        **base,
        AUTH_FRONTEND_BASE_URL="https://commerce.example",
        EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
    )
    assert console_backend.returncode != 0
    assert "delivery-capable EMAIL_BACKEND" in console_backend.stderr

    readable_console_backend = run_settings_probe(
        **base,
        AUTH_FRONTEND_BASE_URL="https://commerce.example",
        EMAIL_BACKEND="accounts.mail.ReadableConsoleEmailBackend",
    )
    assert readable_console_backend.returncode != 0
    assert "delivery-capable EMAIL_BACKEND" in readable_console_backend.stderr

    local_sender = run_settings_probe(
        **{**base, "DEFAULT_FROM_EMAIL": "noreply@localhost"},
        AUTH_FRONTEND_BASE_URL="https://commerce.example",
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
    )
    assert local_sender.returncode != 0
    assert "non-local DEFAULT_FROM_EMAIL" in local_sender.stderr


def test_verification_intervals_are_validated():
    result = run_settings_probe(
        COMMERCE_ENV="development",
        DJANGO_SECRET_KEY="django-insecure-development-only-not-for-production",
        AUTH_EMAIL_VERIFICATION_TTL_SECONDS="0",
    )

    assert result.returncode != 0
    assert "TTL_SECONDS must be positive" in result.stderr


def test_password_recovery_intervals_are_validated():
    base = {
        "COMMERCE_ENV": "development",
        "DJANGO_SECRET_KEY": "django-insecure-development-only-not-for-production",
    }
    invalid_ttl = run_settings_probe(
        **base,
        AUTH_PASSWORD_RECOVERY_TTL_SECONDS="0",
    )
    invalid_cooldown = run_settings_probe(
        **base,
        AUTH_PASSWORD_RECOVERY_RESEND_COOLDOWN_SECONDS="-1",
    )
    assert invalid_ttl.returncode != 0
    assert "AUTH_PASSWORD_RECOVERY_TTL_SECONDS must be positive" in invalid_ttl.stderr
    assert invalid_cooldown.returncode != 0
    assert "AUTH_PASSWORD_RECOVERY_RESEND_COOLDOWN_SECONDS cannot be negative" in invalid_cooldown.stderr
