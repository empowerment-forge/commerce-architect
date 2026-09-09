# Current Architecture

This is the canonical current runtime architecture. Historical design context is
retained in [ARCHITECTURE_v1.2.md](ARCHITECTURE_v1.2.md).

```text
Browser
  │ HTTPS
  ▼
Frontend: NGINX + React assets
  ├── /             SPA and fallback
  ├── /api/         private proxy to Django
  ├── /admin/       private proxy to Django
  └── /static/      private proxy to Django/WhiteNoise
                          │
                          ▼
                   Backend: Gunicorn + Django/DRF
                          │
                          ▼
                   Private persistent PostgreSQL
```

## Boundaries

- `frontend/` owns the React/Vite browser application and NGINX public edge.
- NGINX rejects dotfile paths before SPA fallback and keeps `/api/`, `/admin/`,
  and `/static/` routing explicit.
- `backend/accounts/` owns authentication and remains independent of commerce
  domains.
- `backend/catalog/` owns the current commerce-domain API.
- `backend/health/` owns database-aware readiness.
- Django/WhiteNoise owns Django static files; the frontend image does not.
- PostgreSQL owns persistent state and should remain privately reachable.

The browser and API share one HTTPS origin. The frontend and backend may be
deployed independently, but cross-site browser authentication is not a current
requirement. Authentication uses short-lived JWT access tokens in memory and
rotating refresh tokens in secure HttpOnly cookies; see
[USERAUTH_ARCHITECTURE.md](USERAUTH_ARCHITECTURE.md).

## Application structure

- Django 6.1 and Django REST Framework provide the backend API. Django apps own
  domain boundaries: `accounts`, `catalog`, and `health`.
- PostgreSQL 16 is the authoritative relational store. Django migrations own
  schema evolution; they do not imply seed data or privileged-user creation.
- React, TypeScript, Vite, and Tailwind CSS provide the browser application.
  React owns presentation and client interaction; Django remains authoritative
  for business rules, validation, authentication, and authorization.
- API serializers control exposed representations and validate transport data.
  Views stay thin; domain rules belong in models or domain services.

The current catalog slice exposes `GET /api/products/`. Its product model uses
decimal pricing, an active flag for soft deactivation, and a product type for
future domain specialization. See [UX_ARCHITECTURE.md](UX_ARCHITECTURE.md) for
the frontend direction and [ROADMAP.md](ROADMAP.md) for future commerce work.

## Deployment architecture

The frontend and backend are independently built OCI images. A deployment must
provide HTTPS ingress, runtime configuration, private service networking,
persistent PostgreSQL, pre-activation migrations, and health gates. The current
frontend NGINX image provides same-origin routing to Django.

GitHub Actions validates the exact production images and preserves immutable
artifact identity. Provider selection, environment names, domains, credentials,
and operator procedures are deployment-specific rather than application
architecture. See [BUILD_DEPLOY.md](BUILD_DEPLOY.md).

Hosted development uses production security behavior with non-production
credentials and no real customer commerce data. Local Compose remains a
separate developer topology.
