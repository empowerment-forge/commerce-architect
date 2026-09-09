import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def use_in_memory_email_backend(settings):
    cache.clear()
    settings.MAILERS = {
        "default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}
    }
    settings.AUTH_FRONTEND_BASE_URL = "http://localhost:5173"
    settings.AUTH_REQUIRE_VERIFIED_EMAIL = False
    yield
    cache.clear()
