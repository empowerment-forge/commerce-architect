import importlib

from django.test import override_settings

import pytest

from django.core.exceptions import ImproperlyConfigured
from django.urls import clear_url_caches
from media_storage.configuration import validate_media_settings
from media_storage.configuration import get_media_storage
from media_storage.local import LocalMediaStorageAdapter


def test_disabled_media_has_no_fallback():
    with override_settings(MEDIA_STORAGE_BACKEND="disabled"):
        validate_media_settings()


def test_production_rejects_local_media():
    with override_settings(
        MEDIA_STORAGE_BACKEND="local",
        MEDIA_PUBLIC_BASE_URL="https://media.example",
        MEDIA_LOCAL_ROOT="/var/lib/media",
        IS_PRODUCTION=True,
    ):
        with pytest.raises(ImproperlyConfigured):
            validate_media_settings()


@pytest.fixture
def development_media_urlconf(settings):
    import config.urls

    original_environment = settings.COMMERCE_ENV
    original_is_production = settings.IS_PRODUCTION
    original_backend = settings.MEDIA_STORAGE_BACKEND
    settings.COMMERCE_ENV = "development"
    settings.IS_PRODUCTION = False
    settings.MEDIA_STORAGE_BACKEND = "local"
    importlib.reload(config.urls)
    clear_url_caches()
    try:
        yield
    finally:
        settings.COMMERCE_ENV = original_environment
        settings.IS_PRODUCTION = original_is_production
        settings.MEDIA_STORAGE_BACKEND = original_backend
        importlib.reload(config.urls)
        clear_url_caches()


@pytest.mark.django_db
def test_development_media_route_serves_get_and_head_without_listing(
    client, tmp_path, settings, development_media_urlconf
):
    settings.MEDIA_STORAGE_BACKEND = "local"
    settings.MEDIA_LOCAL_ROOT = str(tmp_path / "media")
    get_media_storage.cache_clear()
    stored = LocalMediaStorageAdapter(settings.MEDIA_LOCAL_ROOT).put_if_absent(b"route-bytes", "image/png")
    response = client.get(f"/media/{stored.storage_key}")
    assert response.status_code == 200
    assert response.content == b"route-bytes"
    assert response["X-Content-Type-Options"] == "nosniff"
    head = client.head(f"/media/{stored.storage_key}")
    assert head.status_code == 200
    assert head["Content-Length"] == str(len(b"route-bytes"))
    get_media_storage.cache_clear()
