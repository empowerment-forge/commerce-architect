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

Third-party: - rest_framework - Simple JWT blacklist - WhiteNoise

Project apps: - accounts - catalog - health

------------------------------------------------------------------------

# Database Configuration

Configured in settings.py using environment variables:

`backend/config/settings.py` reads `DATABASE_NAME`, `DATABASE_USER`,
`DATABASE_PASSWORD`, `DATABASE_HOST`, and `DATABASE_PORT`. Local Compose supplies
development values; hosted environments use Railway references. Do not copy
rendered database credentials into source or documentation.

`COMMERCE_ENV` selects development or production security behavior. Hosted
development intentionally uses `COMMERCE_ENV=production`, `DEBUG=False`,
Gunicorn, WhiteNoise compressed-manifest static assets, and explicit hosts and
origins. `GET /health/` checks database availability.

------------------------------------------------------------------------

# Architectural Pattern

Django apps represent domains.

Each domain app contains: - models - migrations - serializers - views -
urls

Business logic belongs in models or domain services.

Views remain thin.
