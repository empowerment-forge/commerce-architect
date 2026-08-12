# Commerce Architect Build & Deployment

## Purpose

The immediate objective is to launch and operate
[https://dev-commerce.empowerment-forge.com](https://dev-commerce.empowerment-forge.com)
as Commerce Architect's first production-style development deployment.
Proving deployability, security, recoverability, and operational discipline
comes before expanding into Orders, Inventory, Checkout, or other business
domains.

This is the authoritative build, deployment, security, and operations guide for
that milestone. It describes the **CURRENT** repository state, the **PLANNED**
target, and **OPEN DECISIONS** that must be resolved during implementation. It
does not claim that planned controls or deployment automation already exist.

Security and protection of data are primary architecture requirements, not
post-launch enhancements.

## Environment Model

### Local Development

**CURRENT:** The shared `docker-compose.yml` runs PostgreSQL 16, Django/DRF via
the development `runserver`, and React via the Vite development server. It is
compatible with Docker Compose and Podman Compose. Source is bind-mounted, the
database uses a named volume, and safe local-only example credentials support
developer convenience. Native frontend development is also documented.

This topology is for local development only. Its exposed ports, default local
credentials, Django `runserver`, Vite server, and mutable bind mounts are not a
hosted runtime design.

### Development Deployment

**PLANNED:** `dev-commerce.empowerment-forge.com` will be an internet-facing,
production-style **non-production** Railway environment. It must be HTTPS-only,
contain no real customer data or production credentials, and use real security,
secrets, database, backup, testing, deployment, and operational controls.

The Django runtime must use its production security behavior even though the
Railway environment is named `development` and its data and business purpose
are non-production:

```text
COMMERCE_ENV=production
DJANGO_DEBUG=false
```

The Railway environment name and Django security mode are separate concepts.
This intentional configuration requires a strong `DJANGO_SECRET_KEY`, disables
debug behavior, requires real `DJANGO_ALLOWED_HOSTS`, enables secure cookie
behavior, and supports running Django deployment security checks. Environment
names must not weaken runtime security expectations.

### Future Public Demo / Production

**TBD:** A future public or production environment might use
`https://commerce.empowerment-forge.com`, but the name, topology, promotion
policy, isolation model, and release process are not final. It must use distinct
credentials, secrets, databases, backups, and access controls from hosted dev.

## Current Application Components

- **CURRENT — frontend:** React 19 and TypeScript, with Vite for development and
  builds, Vitest, React Testing Library, ESLint, and a product-list UI.
- **CURRENT — backend:** Django 6 and Django REST Framework, organized under
  `backend/`, with catalog, accounts, and health capabilities.
- **CURRENT — authentication:** SimpleJWT access tokens plus a rotating,
  blacklisted refresh token in an HttpOnly cookie. Production settings make the
  refresh cookie `Secure`; access tokens have a 10-minute lifetime and refresh
  tokens a 7-day lifetime.
- **CURRENT — database:** PostgreSQL 16 in local Compose; Django migrations
  define schema evolution.
- **CURRENT — containers:** a production backend image and development Compose
  setup; the frontend has only `Dockerfile.dev`.
- **CURRENT — CI:** GitHub Actions runs frontend tests and builds the production
  backend image once, validates and scans that image against disposable
  PostgreSQL, then publishes/deploys it only for successful `develop` pushes.

## Deployable Artifacts

### Frontend

**CURRENT:** `frontend/Dockerfile` is a multi-stage production build. Its Node
24 stage runs `npm ci`, Vitest, ESLint, and the TypeScript/Vite production
build. The NGINX runtime stage contains only NGINX, the generated `dist/`
assets, and the reviewed server template. Railway never runs the Vite
development server or `vite preview`.

NGINX serves the SPA with `index.html` fallback and proxies `/api/` unchanged
to Django over Railway private networking. Runtime Railway references provide
`BACKEND_HOST=${{backend.RAILWAY_PRIVATE_DOMAIN}}` and
`BACKEND_PORT=${{backend.PORT}}`; no private address is baked into the image.
NGINX preserves the public Host and forwards client/proxy addressing and HTTPS
headers so Django evaluates requests as originating at the public application
hostname.

**OPEN DECISION:** Production caching/compression and content-security-policy
tuning remain future work after the first end-to-end deployment is proven.

### Backend

**CURRENT:** `backend/Dockerfile` produces the hosted backend OCI image. It
installs the reviewed Python requirements, copies the Django application, drops
to the unprivileged `commerce` user, and starts the existing WSGI application
with Gunicorn. `backend/gunicorn.conf.py` binds to Railway's injected `PORT`
(default `8000`), emits access/error logs to standard streams, and supplies
conservative initial worker and timeout defaults. Secrets and environment
configuration are injected at runtime and are not image layers.

Local Compose intentionally continues to override the image command with
Django `runserver` for local development only. Hosted Railway deployments use
the image `CMD`; they never use `runserver`.

**OPEN DECISION:** Dependency-locking improvements, static-file handling, and
evidence-based Gunicorn worker/timeout tuning remain future work.

### Database

**CURRENT:** PostgreSQL data is persistent runtime state, not an ephemeral
application artifact. Local Compose stores it in `postgres_data`. Django
migration files are version-controlled and define schema evolution.

**PLANNED:** The hosted environment will use a Railway PostgreSQL database with
network access, credentials, persistence, migration execution, backup,
retention, restore testing, and rollback behavior explicitly configured and
verified. Application images must never contain database data.

**VERIFY BEFORE LAUNCH:** Railway's current persistence, encryption, backup,
retention, restore, network-isolation, credential-rotation, and recovery
capabilities for the selected plan. Record verified provider behavior and any
application-owned compensating controls.

## Target Runtime Architecture

**CURRENT:** Railway hosts the NGINX/React frontend, Gunicorn/Django backend,
and persistent PostgreSQL service. `dev-commerce.empowerment-forge.com` belongs
to the existing Railway `frontend` service and is the public application entry
point. NGINX serves the SPA and routes `/api/` to
`backend.railway.internal` through Railway private networking. Django reaches
PostgreSQL privately. Image configuration uses Railway references rather than
hard-coded private hostnames or ports.

The temporary Railway backend public domain remains during initial end-to-end
verification. Once public frontend and private `/api/` behavior are proven and
an operational access path is retained, it can be removed separately.

## Railway

**SELECTED:** Railway is the deployment target for
`dev-commerce.empowerment-forge.com`. The provider decision is not reopened
unless implementation uncovers a hard technical blocker.

Design goals are a simple initial deployment, PostgreSQL support, GitHub/CI
integration, environment-variable and secret injection, custom-domain support,
useful logs and health visibility, and portability. Provider-specific support
for each goal must be verified during implementation.

Use standard OCI images, environment configuration, PostgreSQL, and portable
application health checks where practical. Avoid proprietary SDKs or database
features when standard mechanisms satisfy the requirement. Keep DNS under
independent control and document data export and migration paths.

### Canonical Environment Provisioning Baseline

Use the same sequence for every hosted environment: development,
implementation, UAT, and production. Only parameter values may differ, such as
project/environment/service names, domains, secrets, region and capacity, and
whether optional synthetic demo data is loaded. The procedure is operator- and
tool-independent; the Railway CLI commands below are one reproducible way to
perform it.

1. Create or select the Railway project and target environment, then verify the
   exact target before changing it.
2. List existing services and confirm that the target does not already contain
   its PostgreSQL service.
3. Provision one Railway-managed PostgreSQL service:

   ```sh
   railway link --project <project-id-or-name> --environment <environment-name> --json
   railway service list --json
   railway add --database postgres --json
   ```

4. Read back the service, generated variables, persistent volume, and network
   exposure. Store credentials only in Railway; do not copy secret values into
   source control, documentation, command history, or application images.
5. Keep PostgreSQL on Railway's private network. Do not add a public TCP proxy
   unless a reviewed operational requirement documents why private access or an
   authenticated tunnel is insufficient, who may use it, and how it is removed.
6. Configure the future Django service using Railway variable references that
   map the managed PostgreSQL service variables into Django's existing
   `DATABASE_*` configuration contract:

   ```sh
   railway variable set \
     DATABASE_HOST='${{Postgres.PGHOST}}' \
     DATABASE_NAME='${{Postgres.PGDATABASE}}' \
     DATABASE_USER='${{Postgres.PGUSER}}' \
     DATABASE_PASSWORD='${{Postgres.PGPASSWORD}}' \
     DATABASE_PORT='${{Postgres.PGPORT}}' \
     --service <django-service>
   ```

   Expressions such as `${{Postgres.PGHOST}}` are Railway variable references,
   not copied values. They do not rename or modify Railway's PostgreSQL
   variables; they expose those values under the names Django already reads.
   Secret values must remain in Railway and must not be copied into source
   control or documentation. `Postgres` is the exact, case-sensitive database
   service name and must be replaced if a different canonical service name is
   chosen. Django does not currently consume `DATABASE_URL`.
7. Configure the remaining environment values. In the internet-facing hosted
   development environment, set `COMMERCE_ENV=production` and
   `DJANGO_DEBUG=false`. The Railway environment name `development` identifies
   the deployment/configuration scope; it does not select Django's security
   mode. Production security mode intentionally requires a strong
   `DJANGO_SECRET_KEY`, disables debug behavior, requires real
   `DJANGO_ALLOWED_HOSTS`, enables secure cookie behavior, and supports Django
   deployment security checks.
8. Build/deploy the reviewed immutable application artifacts and verify health
   and exposure.
9. Run reviewed Django migrations as a controlled deployment operation. Django
   migration files remain the sole authority for application schema creation
   and evolution; provisioning PostgreSQL must not create application schema.
10. Load required initial data or optional synthetic demo/catalog data only as a
   separate, explicit, idempotent operation after migrations. Data loading is
   not a schema migration and may be omitted by environment policy.
11. Verify backup/restore controls, monitoring, access, and recovery behavior
    before declaring the environment ready.

Never make development structurally special. Development may use different
values or opt into synthetic demo data, but it follows the same provisioning,
migration, verification, and security sequence as implementation, UAT, and
production.

### Current Development PostgreSQL Evidence

**CURRENT (2026-08-11):** Railway project `empowerment-forge.com`, environment
`development`, contains managed service `Postgres` with a persistent volume at
`/var/lib/postgresql/data`. Railway reports the service deployment healthy and
the volume ready. The service has a private network endpoint and no public TCP
proxy. No Django service, application schema migration, or catalog seed/demo
load was performed as part of database provisioning.

Railway created the database configuration variables `DATABASE_URL`, `PGDATA`,
`PGDATABASE`, `PGHOST`, `PGPASSWORD`, `PGPORT`, `PGUSER`, `POSTGRES_DB`,
`POSTGRES_PASSWORD`, and `POSTGRES_USER`, plus Railway service/environment and
volume metadata variables and template settings. Secret values are intentionally
not recorded here.

### Current Development Backend Service

**CURRENT (2026-08-11):** Railway service `backend` is provisioned in project
`empowerment-forge.com`, environment `development`. Image auto-updates are
disabled because GitHub Actions is the deployment control plane. The service
uses these runtime controls:

- Railway-generated domain `backend-development-3edc.up.railway.app`.
- Postgres reference-variable mapping from the canonical baseline above.
- `COMMERCE_ENV=production` and `DJANGO_DEBUG=false`.
- Exact allowed hosts `backend-development-3edc.up.railway.app` and
  `healthcheck.railway.app`; the latter is Railway's deployment-healthcheck
  hostname.
- Trusted origins `https://backend-development-3edc.up.railway.app` and
  `https://dev-commerce.empowerment-forge.com`.
- `DJANGO_TRUST_FORWARDED_PROTO=true` so Django can recognize HTTPS terminated
  by Railway's proxy while retaining secure redirect/cookie behavior.
- A strong environment-unique `DJANGO_SECRET_KEY` stored only in Railway.
- Pre-deploy command `python manage.py migrate --noinput`.
- Healthcheck path `/health/` with a 300-second timeout.

The temporary private image source ending in `:bootstrap` exists only so an
operator can enter Railway's separate read-only GHCR Registry Credential before
the first release. It is not a release identity and no bootstrap image is
published. The first successful `develop` release replaces it with a
digest-qualified image reference.

The backend's Railway public domain is intentional only for initial backend
deployment and smoke testing. The target development architecture has
`dev-commerce.empowerment-forge.com` as the sole public application entry point:
frontend NGINX receives browser traffic and proxies `/api` to Django over
Railway private networking. After that proxy path and its health/operational
access are verified, reconsider and normally remove the backend public domain,
then remove it from `DJANGO_ALLOWED_HOSTS` and
`DJANGO_CSRF_TRUSTED_ORIGINS`. Keep `healthcheck.railway.app` allowed while
Railway deployment healthchecks require it.

## DNS and TLS

The target hostname is `dev-commerce.empowerment-forge.com`. DNS for
`empowerment-forge.com` is managed separately through Cloudflare.

**PLANNED:** Document the final Railway/Cloudflare wiring after Railway assigns
and verifies the service endpoint. Do not predeclare DNS record types, proxy
modes, or certificate ownership. HTTPS is mandatory, HTTP must redirect to
HTTPS where applicable, and certificate issuance/renewal and end-to-end TLS
behavior must be tested. Trust forwarded protocol headers only from the known
deployment proxy path.

**OPEN DECISION:** Cloudflare proxy mode versus DNS-only behavior, Railway
custom-domain attachment, TLS termination boundaries, API hostname/routing,
certificate responsibility, and safe HSTS rollout.

## Configuration and Secrets

**CURRENT:** Django requires explicit `COMMERCE_ENV`. Its production branch
requires a strong `DJANGO_SECRET_KEY`, forces `DEBUG=False`, rejects wildcard or
local-only `DJANGO_ALLOWED_HOSTS`, requires database fields, enables secure
session/CSRF/refresh cookies, defaults to HTTPS redirect, and can trust a
forwarded HTTPS header only when explicitly enabled. `CSRF_TRUSTED_ORIGINS` is
environment-driven. The frontend development server proxies `/api` using
`VITE_API_PROXY_TARGET`; a deployed frontend API-base contract is not defined.

**PLANNED principles:**

- Keep every secret out of Git, images, build logs, browser bundles, and
  documentation. `.env.example` contains placeholders or safe local examples,
  never real secrets.
- Give hosted dev a unique Django `SECRET_KEY`, database credentials, JWT
  signing configuration where separately introduced, and third-party secrets.
  Never reuse future production values.
- Configure exact allowed hosts, CORS origins, CSRF trusted origins, cookie
  behavior, proxy trust, frontend API base URL, and environment designation for
  the chosen topology.
- Use least-privilege credentials, restrict who can read/change them, record
  ownership, and make rotation possible without exposing values.
- Treat Vite-prefixed build variables as public because they are embedded in
  frontend assets.
- Validate configuration before deployment and after rotation; prevent secrets
  from appearing in errors or diagnostic output.

**OPEN DECISION:** Exact Railway secret-management workflow, operator access,
rotation procedure, emergency revocation, and whether a standard external
secret manager is needed later.

## Build Pipeline

**CURRENT frontend path:** GitHub Actions builds
`ghcr.io/empowerment-forge/commerce-architect-frontend:<git-sha>` exactly once.
The Docker build itself runs `npm ci`, Vitest, ESLint, and the Vite production
build. CI then uses that exact runtime image to validate NGINX configuration,
container startup, `/`, SPA fallback, and an `/api/` proxy request to a
controlled backend target before applying the Trivy fixed high/critical gate.
For `develop` pushes, the validated image is transferred to the publish job as
a one-day workflow artifact and loaded without rebuilding.

**CURRENT backend path:** GitHub Actions builds
`ghcr.io/empowerment-forge/commerce-architect-backend:<git-sha>` exactly once.
Before publication, the workflow uses that local image to:

1. Run backend pytest against disposable PostgreSQL.
2. Run `python manage.py check` and `python manage.py check --deploy` with
   production-mode, CI-only configuration.
3. Apply migrations to the disposable database.
4. Start Gunicorn from the image and require `/health/` to report both
   application and database readiness using Railway's healthcheck hostname.
5. Fail on fixed high/critical image vulnerabilities reported by Trivy.

For a `develop` push only, the validated image is exported as a short-lived
workflow artifact. The publish job loads that artifact; it does not rebuild the
image. The handoff artifact has a one-day retention period and is not a release
artifact or deployment identity. Frontend tests are also required before
backend publication/deployment. The existing frontend lint and
production-build gates remain planned.

Every required gate must fail closed. Pin or otherwise govern build actions and
tools, protect build credentials, generate useful provenance where practical,
and do not grant pull-request code access to deployment secrets.

## Deployment Pipeline

**CURRENT frontend sequence:** A successful `develop` push publishes only the
validated SHA-tagged image, resolves its GHCR digest, and configures the
existing Railway `frontend` service with:

```text
ghcr.io/empowerment-forge/commerce-architect-frontend@sha256:<digest>
```

The service keeps its existing `dev-commerce.empowerment-forge.com` custom
domain. Railway image auto-update is disabled, `/` gates deployment health for
300 seconds, and the workflow requires the digest-specific deployment to reach
`SUCCESS`. Feature branches, pull requests, `main`, and manual validation runs
cannot publish or deploy to shared development.

**CURRENT backend sequence:** A successful push/merge to `develop`, after all
required validation jobs pass, authenticates to GHCR with the job-scoped
`GITHUB_TOKEN` and `packages: write`. It pushes only the immutable commit tag,
resolves the registry digest, and changes Railway's source to:

```text
ghcr.io/empowerment-forge/commerce-architect-backend@sha256:<digest>
```

The repository secret `RAILWAY_TOKEN` contains a project token scoped to the
development environment. It authorizes only the image-source update and
deployment-status reads. Railway image auto-update is disabled. The workflow
waits for Railway's terminal deployment status and fails unless it is
`SUCCESS`. Job concurrency cancels an obsolete in-progress development release
when a newer `develop` release starts. Pull requests, feature branches,
`workflow_dispatch`, and `main` validation runs cannot publish or deploy.

Railway runs `python manage.py migrate --noinput` from the same digest-qualified
image before starting it. Migration failure prevents activation. Railway then
requires HTTP 200 from `/health/`; failure within 300 seconds prevents traffic
from shifting to the new deployment. Catalog/demo seeding is not part of this
workflow.

**OPEN DECISION:** Environment approvals, broader artifact promotion,
post-deployment authentication/browser tests, and automated rollback remain to
be implemented. Independently triggering frontend and backend deployments by
changed path is a future optimization; this first complete milestone validates
and deploys both images after a successful `develop` push.

## Security

Security and protection of data are primary architecture requirements, not
post-launch enhancements. Hosted dev is non-production in data purpose, not in
defensive quality.

### HTTPS/TLS

Require HTTPS for every browser/API flow, redirect HTTP where applicable, use
secure cookies, validate the proxy trust boundary, test certificate renewal,
and introduce HSTS only after the domain/TLS topology is proven. Do not allow
mixed content or plaintext database connections across untrusted networks.

### Django Production Hardening

Run with `COMMERCE_ENV=production` and `DEBUG=False`; run both ordinary and
deployment checks; reject unsafe defaults; use a production WSGI/ASGI server;
minimize exposed endpoints; and review admin, error pages, static files,
clickjacking protection, proxy headers, and security middleware. Exact settings
must be verified against the deployed proxy topology.

### Host, CORS, and CSRF Boundaries

Use exact `ALLOWED_HOSTS`; never use `*`. Prefer same-origin/same-site topology
to reduce cross-origin complexity. If cross-origin calls are required, add and
test the minimum CORS allowlist, credentials behavior, preflight policy, and
CSRF trusted origins. CORS is not an authorization control. Keep CSRF middleware
enabled and test every cookie-authenticated state-changing request.

### JWT and Authentication

Validate the current access-token/HttpOnly refresh-cookie model over real HTTPS:
issuance, expiry, authorization, rotation, replay rejection after blacklisting,
logout, cookie `Secure`/`HttpOnly`/`SameSite`/path attributes, CSRF behavior,
clock assumptions, and invalid-token handling. Do not log tokens. Review signing
key ownership and rotation, revocation retention, concurrent refresh behavior,
and account enumeration.

Password and account controls require Django validators, secure password
hashing, generic authentication errors, brute-force/credential-stuffing
protection, safe recovery/verification when implemented, and privileged-account
discipline. **OPEN DECISION:** rate limiting and broader abuse protection,
including whether controls live in Django, Cloudflare, Railway, or layered
mechanisms.

### Secrets and Least Privilege

Restrict deployment, database, GitHub, Railway, Cloudflare, and future
third-party credentials by role and environment. Separate build from deploy
authority, keep secrets out of artifacts and logs, rotate them, remove stale
access promptly, and audit configuration changes. The application database role
must receive only required privileges.

### Secure Logging and Headers

Log actionable events without passwords, tokens, cookies, secret values,
database URLs, or unnecessary personal data. Sanitize exceptions and request
metadata. Define retention and access controls. Verify appropriate content type,
frame-ancestor/clickjacking, referrer, content security, cache, and transport
headers for both frontend and API; exact CSP and HSTS policy are open decisions.

### Security Assurance

**PLANNED REQUIRED GATES:**

- Dependency and supply-chain scanning for Python, npm, CI actions, and base
  images, with triage and remediation expectations.
- Static/security analysis of Python, TypeScript, configuration, Dockerfiles,
  and CI/deployment definitions.
- Container/image vulnerability and secret scanning where containers apply.
- OWASP-oriented testing informed by the OWASP Top 10 and OWASP Web Security
  Testing Guide, including authentication/session, authorization, input
  validation, injection, security configuration, and dependency/supply-chain
  risks.
- A documented, authorized penetration-testing process with scope, safety
  limits, test accounts/data, evidence handling, remediation, retest, and
  provider-policy review.

Penetration testing has **not** yet been performed. A scoped baseline test and
remediation/retest process are required before launch or before the environment
is treated as ready for ongoing internet-facing use. Continuous automated
testing complements but does not replace manual adversarial review.

## Data Protection

- Never place real customer or future production data in hosted dev. Use
  minimal synthetic test data and periodically remove data no longer needed.
- Restrict PostgreSQL network and account access; use unique least-privilege
  credentials and record administrative access paths.
- Require encryption in transit. **VERIFY BEFORE LAUNCH:** provider/database
  TLS configuration and certificate-validation behavior.
- **VERIFY BEFORE LAUNCH:** Railway-managed encryption at rest, backup storage
  encryption, isolation, retention, deletion, export, and restore guarantees
  for the selected plan. Do not advertise unverified provider guarantees.
- Exclude secrets and unnecessary PII from logs, telemetry, backups, fixtures,
  screenshots, and support artifacts. Apply retention and access controls.
- Back up before risky migrations or destructive operations; protect backups
  separately enough to remain useful after application or credential failure.
- Define recovery point and recovery time targets, retention, ownership,
  restore destination, integrity checks, and scheduled restore drills.
- Use confirmations, peer review/approval where practical, scoped credentials,
  and explicit target checks for destructive database operations.
- Keep hosted dev and future production data, credentials, backups, and access
  paths separate. Future privacy, data-subject, residency, and compliance
  obligations remain to be assessed before collecting real personal data.

## Database Migration Strategy

**CURRENT:** Django migrations are version-controlled schema changes.

**CURRENT:** Railway runs `python manage.py migrate --noinput` as the backend
service pre-deploy command, using the exact candidate image and its private
Postgres reference variables. Migration failure blocks deployment. Seed/demo
data is deliberately excluded.

Treat migrations as reviewed deployment inputs. Inspect generated
SQL/operations when risk warrants it, test against representative disposable
data, identify locks/runtime impact, and coordinate code/schema compatibility.
Back up and verify recovery before destructive or difficult-to-reverse changes.
Never allow multiple deploys to race migrations.

**OPEN DECISION:** Transaction/timeout policy, expand-and-contract conventions,
maintenance needs, and when to forward-fix versus reverse a migration. A code
rollback does not automatically reverse a database migration.

## Rollback Strategy

**PLANNED:** Retain identifiable prior application artifacts and configuration
history so a failed backend deployment or frontend regression can be reverted
to a known-good revision. Health/smoke failures should stop promotion and
trigger the selected manual or automated rollback. Configuration or secret
errors require restoring a known-good configuration or rotating/revoking the
affected value, followed by complete verification.

Bad migrations require a separate recovery plan: prefer backward-compatible
changes and forward fixes when safest; otherwise use a tested reverse migration
or restore/recovery procedure with an explicit data-loss assessment.

**OPEN DECISION:** Artifact retention, Railway rollback mechanism, automatic
thresholds, configuration versioning, database point-in-time capabilities,
recovery targets, and decision authority. Database rollback requires deliberate
design and a drill before launch readiness is claimed.

## Testing Strategy for Hosted Dev

The hosted environment must combine:

- Existing and expanded automated CI unit/integration tests.
- Post-deployment health and database-connectivity checks.
- API contract and negative/authorization tests.
- Browser tests for frontend loading, routing, API access, and failure states.
- Real-HTTPS authentication tests covering login, token expiry/use, refresh,
  logout, cookies, CSRF, CORS, and unauthorized access.
- TLS, redirect, header, host, configuration, and exposure tests.
- Dependency, static, secret, and container/image audits.
- OWASP-oriented dynamic tests and authorized penetration testing.
- Backup restoration and application recovery drills.

Use synthetic accounts/data. Keep active tests safe, rate-bounded, scoped to
owned targets, and coordinated with provider policies. Define which checks run
per pull request, per deployment, on a schedule, and before readiness sign-off.

## Health Checks / Logging / Monitoring

**CURRENT:** `GET /health/` verifies Django can connect to PostgreSQL, returning
HTTP 200 with `{"status":"ok","database":"ok"}` or HTTP 503 when the database
is unreachable. It is covered by backend tests. Current CI waits on PostgreSQL
but there is no documented hosted monitoring or alerting stack.

**CURRENT:** Railway gates backend deployment activation on `GET /health/`
returning HTTP 200 within 300 seconds. Railway sends the hostname
`healthcheck.railway.app`, which is explicitly allowed. The endpoint verifies
Django can connect to PostgreSQL and returns HTTP 503 if it cannot.

Distinguish, if needed, process liveness from dependency readiness. Capture
deployment logs, application errors, database connectivity failures,
latency/availability, and suspicious authentication activity. Alert the
responsible operator with a documented response path. Logs must omit secrets,
tokens, cookies, credentials, database URLs, and unnecessary personal data, and
must have access and retention controls.

**OPEN DECISION:** Logging destination, structured fields/correlation IDs,
metrics and uptime checks, alert thresholds/channels, retention, on-call
expectations, and whether `/health/` should be split into liveness/readiness.

## Release and Promotion Strategy

**CURRENT concept:** feature branches merge by reviewed pull request into
`develop`; `main` is the publication/release branch.

**PLANNED for hosted dev:** `feature -> develop -> dev deployment`. A specific
successful `develop` revision and its immutable artifacts must be identifiable
in Railway. Deployment authority, approvals, and rollback ownership must be
documented.

**FUTURE/TBD:** Promotion toward a possible
`commerce.empowerment-forge.com` environment must reuse verified artifacts where
practical while applying separate production configuration and secrets. No
production release process or topology is defined here.

## Operational Checklist

Security and data protection are launch blockers, so they appear first.

- [ ] Confirm no real customer data or production credentials are present.
- [ ] Complete threat review and document public attack surface and ownership.
- [ ] Verify HTTPS-only behavior, certificates, redirects, proxy trust, security
      headers, exact hosts/origins, and secure cookie attributes.
- [ ] Confirm `COMMERCE_ENV=production`, `DEBUG=False`, strong unique secrets,
      least privilege, and successful Django deployment checks.
- [ ] Complete dependency, static/security, secret, and image scans; triage
      findings to the approved launch threshold.
- [ ] Complete authorized OWASP-oriented security and penetration testing;
      remediate and retest blocking findings.
- [ ] Verify database access restrictions, encrypted connections, provider data
      controls, retention, and environment separation.
- [ ] Create a protected backup and successfully restore it into an isolated
      target; record recovery evidence and timing.
- [ ] Approve production frontend/backend artifacts and serving processes.
- [ ] Confirm all CI gates pass for the exact deployed revision.
- [ ] Validate the migration plan, concurrency guard, and destructive-change
      protections.
- [ ] Configure Railway services, environment values, custom domain, and health
      checks from reviewed records.
- [ ] Run post-deployment health, API, browser, and authentication smoke tests.
- [ ] Confirm logs/monitoring/alerts work and expose no sensitive values.
- [ ] Exercise application/configuration rollback and database recovery paths.
- [ ] Document deploy, migration, rollback, restore, rotation, access, incident,
      and routine maintenance procedures with owners.
- [ ] Record readiness approval, deployed revision, known risks, and follow-up
      actions.

## Open Decisions

- Exact Railway frontend/static-hosting topology and routing.
- Same-origin versus separate frontend/API hostnames.
- Backend worker tuning and backend/frontend static-file handling, caching, and
  compression.
- Deployment approvals beyond the current GitHub-driven development path.
- Immutable artifact registry, identification, retention, and promotion.
- Migration locking/concurrency and forward-fix/rollback policy.
- Railway secret-management mechanics, access control, audit, and rotation.
- Railway PostgreSQL networking, TLS, encryption, backups, retention, export,
  point-in-time recovery, and restore-test procedure for the selected plan.
- Monitoring, logging, uptime checking, alerting, retention, and response owners.
- Dependency, static/security, secret, dynamic, and image-scanning tools and
  finding thresholds.
- Rate limiting and abuse-protection layers.
- Penetration-testing tooling, provider authorization, scope, cadence, evidence
  handling, remediation threshold, and retest process.
- Application, configuration, frontend, and database rollback mechanisms.
- Cloudflare/Railway DNS, proxy, and TLS relationship, including safe HSTS.

Resolve these through documented implementation evidence. Do not silently turn
an open decision into an architectural dependency.
