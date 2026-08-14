# Build and Deployment Contract

This document is the canonical description of how Commerce Architect artifacts
are built, validated, published, and normally deployed. First-time setup belongs
in [ENVIRONMENT_PROVISIONING.md](ENVIRONMENT_PROVISIONING.md); operator and
recovery procedures belong in [OPERATIONS.md](OPERATIONS.md).

## Current hosted environment

`dev-commerce.empowerment-forge.com` is an internet-facing, production-style
**non-production** Railway environment. It uses HTTPS, non-production
credentials, and no real customer data. Railway calls the environment
`development`, while Django deliberately runs its hardened production settings:

```text
COMMERCE_ENV=production
DJANGO_DEBUG=false
```

These names describe different concerns: business/data purpose versus runtime
security mode. See [ARCHITECTURE.md](ARCHITECTURE.md) for the full topology.

## Artifacts and runtime

### Frontend

`frontend/Dockerfile` is a multi-stage production build. Its Node 24 stage runs
locked dependency installation, Vitest, ESLint, and the TypeScript/Vite build.
Only `dist` and the reviewed NGINX configuration enter the runtime image.
Railway never runs the Vite development server.

NGINX listens on Railway's `PORT`, serves the SPA, and proxies `/api/`,
`/admin/`, and `/static/` to the backend through Railway private networking.
The browser client therefore uses same-origin API URLs without a build-time
backend origin. A higher-priority regex location returns 404 for dotfile paths,
including nested paths, so hidden-file probes never receive the SPA fallback or
reach Django. CI checks representative root and nested dotfile requests.

### Backend

`backend/Dockerfile` installs Python dependencies, runs `collectstatic`, switches
to a non-root user, and launches Gunicorn. `backend/gunicorn.conf.py` binds to
Railway's `PORT`. WhiteNoise serves compressed, manifest-versioned Django static
assets through the backend; NGINX only proxies those requests.

`python manage.py migrate --noinput` runs as Railway's backend pre-deploy command
from the same digest-qualified image. Migration failure prevents activation.
`GET /health/` then gates activation and returns 503 if PostgreSQL is unavailable.

### Database

Railway PostgreSQL is persistent application state on a volume mounted at
`/var/lib/postgresql/data`. It is private and has no public TCP domain. Django
uses Railway variable references; rendered credentials are never copied into
source, documentation, or GitHub Actions.

Local Compose PostgreSQL is disposable developer state and is documented only
in [POSTGRES_SETUP.md](POSTGRES_SETUP.md).

## CI trigger matrix

| Event | Validate both images | Publish to GHCR | Deploy hosted development |
|---|---:|---:|---:|
| Pull request targeting `develop` | Yes | No | No |
| Push to `main` | Yes | No | No |
| Push to `develop` | Yes | Yes | Yes |
| Feature-branch push | No | No | No |
| Manual workflow dispatch | Yes | No | No |

The workflow currently validates and deploys both components even when only one
changed. Path-based independent deployment is a future optimization.

## Build once, deploy by digest

For each component, GitHub Actions:

1. Builds the production image once.
2. Runs checks against that exact image.
3. Scans it with Trivy for fixed HIGH/CRITICAL findings.
4. Saves it as a one-day workflow artifact.
5. On a successful `develop` push, reloads and publishes it to GHCR under the
   commit SHA.
6. Resolves the registry digest.
7. Updates the Railway service source to `image@sha256:digest`.
8. Waits for Railway's terminal deployment status and fails unless successful.

The frontend image runs its tests, lint, and production build. The backend image
runs pytest against disposable PostgreSQL, ordinary Django checks, production
deployment checks, migration checks, and an image smoke test. Secrets are not
baked into either artifact.

Dependabot targets `develop` weekly for npm, pip, and GitHub Actions. Routine
minor and patch updates are grouped per ecosystem; major-version updates remain
explicit review work. Dependency manifests intentionally express compatible
ranges, so CI's exact-image validation remains the release gate while a Python
lock/constraints decision remains open.

## Deployment credentials and boundaries

- `GITHUB_TOKEN` publishes packages with the workflow's scoped `packages: write`
  permission.
- A Railway Project Token is stored as GitHub Actions secret `RAILWAY_TOKEN` and
  is available only to deployment jobs on trusted `develop` pushes.
- Railway's backend and frontend Registry Credentials use a separate read-only
  GHCR credential. Image auto-update is disabled so GitHub Actions remains the
  deployment control plane.
- `DJANGO_SECRET_KEY` and database credentials exist only in Railway variables.
- Feature branches and pull requests never receive deployment credentials.

Credential ownership and rotation steps are in [OPERATIONS.md](OPERATIONS.md).

## Current environment contract

The frontend custom domain is `dev-commerce.empowerment-forge.com`. The backend
allows that public host, its current Railway-generated host, and Railway's health
check hostname. Trusted origins include the public HTTPS origin.

Railway terminates public TLS and forwards the original scheme. Django trusts
the reviewed proxy header. Secure cookies remain enabled. The deployed
`DJANGO_SECURE_SSL_REDIRECT` override must match the proven Railway proxy path;
operators must verify it without printing unrelated variables before changing
redirect behavior.

Email verification requires `AUTH_REQUIRE_VERIFIED_EMAIL`, positive token TTL
and non-negative resend-cooldown values, an absolute HTTPS
`AUTH_FRONTEND_BASE_URL`, a delivery-capable `EMAIL_BACKEND`, and a non-local
`DEFAULT_FROM_EMAIL`. Production startup rejects missing or local-only email
settings. Provider credentials remain runtime secrets and must never use a
`VITE_` prefix.

For Railway SMTP delivery, configure service variables—not repository files—with:

```text
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
SMTP_HOST=smtp.resend.com
SMTP_PORT=587
SMTP_USERNAME=resend
SMTP_PASSWORD=<Railway secret variable>
SMTP_USE_TLS=true
SMTP_USE_SSL=false
SMTP_TIMEOUT=10
DEFAULT_FROM_EMAIL=Commerce Architect <accounts@empowerment-forge.com>
AUTH_FRONTEND_BASE_URL=https://dev-commerce.empowerment-forge.com
```

Resend is the tested example; any standards-compatible SMTP provider can use
the same variables. Never commit or print the provider credential. Django 6.1
receives these values through `MAILERS["default"]["OPTIONS"]`; deprecated
`EMAIL_HOST`/`EMAIL_PORT` settings are not used.

The backend's Railway-generated public domain currently remains available as a
temporary operational endpoint. Whether to remove it or retain it in restricted
form is unresolved; do not remove it without evaluating health and emergency
access needs.

## Normal deployment verification

After a `develop` push:

1. Confirm both workflow publish/deploy jobs succeeded.
2. Confirm both Railway services report `SUCCESS` for the expected commit.
3. Confirm each Railway image source contains the GHCR digest resolved for that
   commit.
4. Run the non-destructive acceptance checks in
   [OPERATIONS.md](OPERATIONS.md#post-deployment-acceptance).

Expected unauthenticated behavior includes `/api/auth/me/` returning 401,
`/api/` returning 404 because no API index exists, and `/admin/` redirecting to
login.

## Release and data boundaries

Migrations create and evolve schema; they never imply catalog/demo seeding or
privileged-user creation. No canonical seed-data procedure has been approved.
Hosted superusers are created interactively according to the provisioning
runbook, and passwords must never enter variables, fixtures, shell history, CI,
or documentation.

No production release/promotion mechanism is defined here. `main` validates but
does not publish or deploy. Implementation, UAT, and production must use the same
structural process with separate parameter values, credentials, data, and
approval policy once those environments are approved.

## Unresolved decisions

- Tested backup/PITR capability, retention, RPO/RTO, and restore ownership.
- Application rollback authorization and migration compatibility policy.
- Monitoring, alerts, incident ownership, and service-level objectives.
- Production/UAT promotion and environment-specific workflow parameterization.
- Cloudflare proxy mode, certificate ownership, CSP, and HSTS rollout.
- Backend public-domain removal or restricted retention.
- Capacity, region, replica count, and periodic access-review policy.
- Catalog/demo bootstrap-data policy.

Until rollback and isolated database restore are tested, hosted development is
successfully deployed but is not fully operationally recoverable.
