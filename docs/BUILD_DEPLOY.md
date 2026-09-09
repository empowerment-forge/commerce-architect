# Build and Deployment Contract

This is the canonical provider-neutral contract for building, configuring,
deploying, and operating Commerce Architect. It defines what a deployment must
provide; each adopter owns the provider-specific implementation and runbook.

Commerce Architect can run on any platform that supports OCI containers,
persistent PostgreSQL, private service networking, HTTPS ingress, runtime
secrets, migrations, and health checks.

## Runtime topology

```text
Browser
  │ HTTPS
  ▼
Frontend: NGINX + built React assets
  ├── /             SPA and fallback
  ├── /api/         proxy to Django
  ├── /admin/       proxy to Django
  └── /static/      proxy to Django/WhiteNoise
                          │
                          ▼
                   Backend: Gunicorn + Django/DRF
                          │
                          ▼
                   Private persistent PostgreSQL
```

The browser-facing frontend and API are expected to share an HTTPS origin. A
different-origin deployment requires a deliberate CORS, CSRF, cookie, and
trusted-proxy review.

## Production artifacts

### Frontend

`frontend/Dockerfile` uses Node 24 to install locked dependencies, run Vitest
and ESLint, and build the TypeScript/Vite application. The runtime image contains
only the built assets and reviewed NGINX configuration; it does not run Vite.

NGINX serves the SPA and proxies `/api/`, `/admin/`, and `/static/` to the
backend. Dotfile requests are rejected before SPA fallback. Bare proxy prefixes
use relative redirects so internal hostnames, schemes, and ports do not appear
in public `Location` headers.

The hosting platform must supply the listener port and a privately reachable
backend host and port through runtime configuration.

### Backend

`backend/Dockerfile` installs Python dependencies, runs `collectstatic`, switches
to a non-root user, and launches Gunicorn. WhiteNoise serves compressed,
manifest-versioned Django static assets.

Every release must run `python manage.py migrate --noinput` before activating
the new backend. Migration failure must prevent activation. `GET /health/`
returns 503 when PostgreSQL is unavailable and should gate backend readiness.

### Database

PostgreSQL 16 is required. Hosted data must use persistent storage and private
network access; database credentials must be supplied at runtime. Local Compose
state is separate and documented in [DOCKER_SETUP.md](DOCKER_SETUP.md).

## Environment contract

A production-mode backend uses `COMMERCE_ENV=production`, disables debug, and
requires environment-specific values for:

- Django secret, allowed hosts, and trusted HTTPS origins;
- PostgreSQL host, port, name, user, and password;
- frontend public base URL and authentication policy;
- secure-proxy behavior appropriate to the actual ingress topology;
- a delivery-capable email backend and non-local sender.

When SMTP is selected, configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`,
`SMTP_PASSWORD`, TLS/SSL mode, timeout, and `DEFAULT_FROM_EMAIL`. The application
uses Django's provider-neutral mail interface and has no provider SDK dependency.
Provider credentials must never use a frontend-exposed `VITE_` variable.

Secret values belong in the hosting platform's secret store or another approved
secret manager. Do not bake them into images, commit them, print them in logs, or
copy rendered values into documentation.

## Provisioning requirements

A new environment must provide:

1. One persistent PostgreSQL database with no unnecessary public exposure.
2. One backend service and one frontend service built from the reviewed OCI
   images.
3. Private frontend-to-backend and backend-to-database connectivity.
4. An HTTPS public domain for the frontend, with certificate and DNS ownership
   recorded by the operator.
5. Environment-unique secrets and explicit production security settings.
6. Backend migration and database-aware health gates.
7. Frontend health checking and backend proxy configuration.
8. A controlled image registry and deployment identity, preferably immutable
   image digests.
9. An approved bootstrap-data policy. Migrations do not seed products or create
   privileged users.

Create the first superuser interactively in the backend service after a healthy
deployment. Never store its password in variables, fixtures, CI, shell history,
or documentation.

Provisioning is reproducible only when another authorized operator can build the
images, supply approved configuration, deploy the three runtime tiers, and pass
the acceptance checks without undocumented provider knowledge.

## CI and artifact validation

GitHub Actions validates the production frontend and backend images directly:

1. Build each production image once.
2. Run frontend tests, lint, build, and NGINX/runtime routing checks.
3. Run backend pytest, Django system/deployment checks, migrations, and runtime
   health checks against disposable PostgreSQL.
4. Scan both images with Trivy for fixed HIGH/CRITICAL findings.
5. Preserve deployment identity through immutable image digests.

Pull requests targeting `develop` and manual dispatches run validation. A push
to `develop` also publishes and deploys the validated images for development
acceptance. Merging `develop` to `main` is a promotion event: it must reuse the
exact tested image digests and must not rebuild the application images.

After both development deployments and public smoke checks succeed, CI writes a
small promotion record as an OCI artifact in GHCR. Its tag is the full develop
source SHA, and its payload records that SHA plus the immutable frontend and
backend digests. CI refuses to replace a different record at the same tag.

When a `develop` to `main` pull request opens, release validation resolves the
record tag once and records both the develop SHA and the promotion record's own
OCI manifest digest in a bot-authored pull-request comment. Subsequent changes
to that pull request fail validation instead of silently selecting newer
artifacts. After merge, production retrieves the record by its pinned manifest
digest, verifies both application digests still exist, and deploys the backend
before the frontend. The production workflow has non-canceling concurrency and
does not contain a build step.

The maintained Railway and GitHub implementation is operational automation for
the project maintainers; the runtime contract in this document remains
provider-neutral for adopters.

Feature branches and pull requests must not receive deployment credentials.
Registry and deployment credentials must be narrowly scoped, separated by
purpose, rotated by their owners, and available only to trusted deployment jobs.

## Deployment sequence

For any provider:

1. Build and validate the frontend and backend production images.
2. Publish the approved images to a controlled OCI registry.
3. Resolve and record immutable image digests.
4. Deploy the backend digest, running migrations before activation.
5. Require the backend database health check to pass.
6. Deploy the frontend digest with private backend routing configured.
7. Require the frontend health check to pass.
8. Verify DNS, HTTPS, service identity, and the acceptance endpoints.

Never assume rolling back an application image reverses a database migration.
Before rollback, confirm schema compatibility and identify the last known-good
digests. Prefer a forward fix when compatibility is unknown.

## Deployment acceptance

From an authorized client, verify:

| Request | Expected result |
| --- | --- |
| `GET /` | 200 frontend |
| `GET /a-client-route` | 200 SPA fallback |
| `GET /api/products/` | 200 |
| `GET /api/auth/me/` without credentials | 401 |
| `GET /api/` | 404; no API index exists |
| `GET /admin/` | redirect to login |
| representative `/static/admin/...` asset | 200 |
| backend `GET /health/` | 200 with database status `ok` |

Also verify that bare `/api`, `/admin`, and `/static` redirects remain relative,
that PostgreSQL has persistent private storage, and that running services match
the intended image digests. Expected 401, 404, and redirect responses are not
deployment failures.

Authentication or email changes require feature-specific acceptance beyond
these route checks. Distinguish CI validation, deployment success, and human UAT
according to [VALIDATION_STANDARDS.md](VALIDATION_STANDARDS.md).

## Operational requirements

Operators must maintain provider-specific private procedures for:

- deployment status, logs, and sanitized diagnosis;
- credential inventory, ownership, least scope, and rotation;
- migration failure and rollback decisions;
- interactive superuser administration;
- monitoring, alerts, incident ownership, and service objectives;
- backup retention, RPO/RTO, and isolated restoration tests;
- DNS, certificate, trusted-proxy, CSP, and HSTS changes;
- capacity, region, replicas, access review, and data policy.

Do not treat hosted data as recoverable until an isolated restore has been
successfully exercised. Do not claim a deployment is accepted until its health,
identity, routing, and relevant user journeys have been verified.

## Release and data boundaries

The repository's release identity is the pinned tuple of develop source SHA,
frontend digest, and backend digest. A later semantic version tag can be applied
to the resulting main release commit without changing those artifact identities.
Development, UAT, and production use separate configuration, credentials, data,
domains, and approval policy.

Commerce Architect is currently an early-stage platform. Backup/restore,
rollback, monitoring, and incident-response maturity remain required before
revenue-critical workloads or real customer commerce data depend on it.
