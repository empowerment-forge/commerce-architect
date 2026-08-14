import pytest


@pytest.fixture(autouse=True)
def use_in_memory_email_backend(settings):
    settings.MAILERS = {
        "default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}
    }
    settings.AUTH_FRONTEND_BASE_URL = "http://localhost:5173"
    settings.AUTH_REQUIRE_VERIFIED_EMAIL = False
