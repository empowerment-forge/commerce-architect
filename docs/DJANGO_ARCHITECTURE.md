# Django Architecture & Configuration

## Version

Django 6.x

------------------------------------------------------------------------

# Project Structure

Created using:

    cd backend
    django-admin startproject config .

(See `backend/config/settings.py`.)

Structure:

-   `backend/config/` → project settings
-   `backend/accounts/` → account and authentication app
-   `backend/catalog/` → catalog domain app
-   `backend/health/` → health endpoint
-   `backend/manage.py` → Django command entry point

------------------------------------------------------------------------

# Installed Applications

Core Django: - admin - auth - contenttypes - sessions - staticfiles

Third-party: - rest_framework

Domain: - catalog

------------------------------------------------------------------------

# Database Configuration

Configured in settings.py using environment variables:

DATABASES = { "default": { "ENGINE": "django.db.backends.postgresql",
"NAME": os.environ.get("DATABASE_NAME"), "USER":
os.environ.get("DATABASE_USER"), "PASSWORD":
os.environ.get("DATABASE_PASSWORD"), "HOST":
os.environ.get("DATABASE_HOST"), "PORT": "5432", } }

Docker provides these values.

------------------------------------------------------------------------

# Architectural Pattern

Django apps represent domains.

Each domain app contains: - models - migrations - serializers - views -
urls

Business logic belongs in models or domain services.

Views remain thin.
