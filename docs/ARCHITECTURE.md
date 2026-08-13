# Current Architecture

This is the canonical current runtime architecture. Historical design context is
retained in [ARCHITECTURE_v1.2.md](ARCHITECTURE_v1.2.md).

```text
Browser
  │ HTTPS
  ▼
dev-commerce.empowerment-forge.com
  │
  ▼
Railway frontend: NGINX + React assets
  ├── /             SPA and fallback
  ├── /api/         private proxy to Django
  ├── /admin/       private proxy to Django
  └── /static/      private proxy to Django/WhiteNoise
                          │
                          ▼
                   Railway backend
                   Gunicorn + Django/DRF
                          │
                          ▼
                 private Railway PostgreSQL
                    persistent volume
```

## Boundaries

- `frontend/` owns the React/Vite browser application and NGINX public edge.
- `backend/accounts/` owns authentication and remains independent of commerce
  domains.
- `backend/catalog/` owns the current commerce-domain API.
- `backend/health/` owns database-aware readiness.
- Django/WhiteNoise owns Django static files; the frontend image does not.
- PostgreSQL is private persistent state. Railway variables reference its
  credentials without copying them.

The browser and API share one HTTPS origin. The backend may be independently
deployable, but cross-site browser authentication is not a current requirement.
Authentication uses short-lived JWT access tokens in memory and rotating
refresh tokens in secure HttpOnly cookies; see
[USERAUTH_ARCHITECTURE.md](USERAUTH_ARCHITECTURE.md).

## Deployment architecture

GitHub Actions builds and validates each image once, publishes successful
`develop` artifacts to GHCR by commit SHA, resolves immutable digests, and tells
Railway to deploy those digests. Railway runs backend migrations before
activation and health-checks both services. See
[BUILD_DEPLOY.md](BUILD_DEPLOY.md).

The Railway environment is called `development`, but Django uses production
security behavior. Hosted development contains no real customer data or
production credentials. Local Compose remains a separate developer topology.
