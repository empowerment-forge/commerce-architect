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

The Django environment should use its production behavior (`COMMERCE_ENV=production`)
even though the data and business purpose are non-production. Environment names
must not weaken runtime security expectations.

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
- **CURRENT — containers:** a backend Dockerfile and development Compose setup;
  the frontend has only `Dockerfile.dev`.
- **CURRENT — CI:** GitHub Actions installs locked frontend dependencies, runs
  frontend tests, builds/starts the Compose database and backend, and runs
  backend pytest tests.

## Deployable Artifacts

### Frontend

**CURRENT:** Vite is development/build tooling. `npm run build` runs the
TypeScript project build and Vite build, producing static assets in
`frontend/dist/` by default. The Vite development server—and `vite preview`—are
not intended as the production runtime.

**PLANNED:** CI will create a reproducible `dist/` artifact and publish or serve
those immutable files using the selected production topology.

**OPEN DECISION:** Choose the Railway-compatible static-serving topology and
define caching, routing/fallback behavior, compression, security headers, and
the frontend-to-API base URL. No production frontend container exists today.

### Backend

**CURRENT:** The Django application source, `backend/requirements.txt`, and
backend Dockerfile form a development container image. The image installs
Python dependencies, but Compose starts it with Django `runserver` and bind
mounts source. Django exposes WSGI and ASGI entry points, but no production
server package or start command is selected.

**PLANNED:** Build an immutable OCI image containing reviewed Django source and
deterministically installed Python dependencies. Run it with a supported
production WSGI or ASGI application server, an explicit start command, safe
process/time-out settings, and a health check. Django `runserver` is not
acceptable for hosted operation.

**OPEN DECISION:** Select the production WSGI/ASGI server and worker model,
dependency-locking approach, static-file handling, startup command, and whether
the existing Dockerfile is adapted or a production-specific build is added.

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

**PLANNED, HIGH LEVEL:** Railway is the selected platform for the first hosted
environment. The intended system contains a static React frontend runtime, a
Django API service built from an immutable OCI image, and a persistent Railway
PostgreSQL service. Cloudflare-managed DNS will connect the custom hostname to
the selected Railway ingress. HTTPS traffic will reach the frontend and API,
with health visibility and controlled frontend-to-API communication.

**OPEN DECISION:** Determine whether frontend and API are served under one
origin or separate hostnames/routes. This choice materially affects routing,
CORS, CSRF, refresh-cookie behavior, TLS, and operational complexity. Prefer a
same-site design unless implementation evidence supports another topology.
Also decide static hosting, internal networking, public API exposure, and
health-check routing only after Railway behavior is verified.

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

**CURRENT:** GitHub Actions checks out source, uses Node 24, runs `npm ci` and
the frontend Vitest suite, builds the backend Compose image, starts PostgreSQL
and Django, and runs pytest. It does not currently lint or build the frontend,
run `manage.py check --deploy`, scan dependencies/source/images, or create
production deployment artifacts.

**PLANNED stages:**

1. Check out the exact source revision.
2. Install locked/reproducible dependencies.
3. Run frontend tests.
4. Run frontend lint.
5. Run frontend type and production-build validation.
6. Run backend tests against PostgreSQL.
7. Run Django system and deployment checks with safe CI-only values.
8. Run dependency and supply-chain scanning plus static/security analysis.
9. Build and scan production container images where applicable.
10. Create immutable, revision-identifiable frontend and backend artifacts.

Every required gate must fail closed. Pin or otherwise govern build actions and
tools, protect build credentials, generate useful provenance where practical,
and do not grant pull-request code access to deployment secrets.

## Deployment Pipeline

**PLANNED sequence:**

1. Require all CI gates to pass for the intended revision.
2. Select/build the immutable, revision-identifiable artifacts or images.
3. Deploy those artifacts to the Railway development environment.
4. Apply reviewed database migrations through the selected safe mechanism.
5. Require service and database health checks.
6. Run frontend and API smoke tests.
7. Verify login, access-token use, refresh rotation, logout, and cookie behavior.
8. Verify TLS, redirects, security headers, host/origin controls, and public
   exposure.
9. Observe application, platform, database, and authentication signals.
10. Mark the deployment successful or invoke the documented rollback path.

**OPEN DECISION:** Railway deploy trigger versus GitHub-driven deployment,
environment approvals, artifact promotion, concurrency control, migration job,
health timeout, and automated rollback. Deployment must prevent an older job
from overwriting a newer successful revision.

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

**PLANNED:** Treat migrations as reviewed deployment inputs. Inspect generated
SQL/operations when risk warrants it, test against representative disposable
data, identify locks/runtime impact, and coordinate code/schema compatibility.
Back up and verify recovery before destructive or difficult-to-reverse changes.
Never allow multiple deploys to race migrations.

**OPEN DECISION:** Migration execution mechanism, transaction/timeout policy,
expand-and-contract conventions, maintenance needs, and when to forward-fix
versus reverse a migration. A code rollback does not automatically reverse a
database migration.

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

**PLANNED:** Use a health signal suitable for Railway routing and deployment
verification while avoiding internal detail leakage. Distinguish, if needed,
process liveness from dependency readiness. Capture deployment logs,
application errors, database connectivity failures, latency/availability, and
suspicious authentication activity. Alert the responsible operator with a
documented response path. Logs must omit secrets, tokens, cookies, credentials,
database URLs, and unnecessary personal data, and must have access and retention
controls.

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
- Django production WSGI/ASGI server and worker model.
- Backend and frontend static-file handling, caching, and compression.
- Railway-native deploy trigger versus GitHub-driven deployment and approvals.
- Immutable artifact registry, identification, retention, and promotion.
- Migration execution, locking/concurrency, and forward-fix/rollback policy.
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
