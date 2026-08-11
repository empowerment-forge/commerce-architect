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
}))
"""


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
