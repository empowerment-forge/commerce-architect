# Commerce Architect Documentation and Operational-Readiness Audit

> **TEMPORARY AUDIT:** Delete this file after all accepted findings have been
> remediated in the canonical repository documentation and the remediation has
> been verified against the implementation and deployed infrastructure.

## A. Executive assessment

Overall rating: **partially reproducible, not yet operator-complete**.

The deployed implementation is coherent and production-like:

- Railway has `frontend`, `backend`, and persistent `Postgres` services.
- Both application services run immutable GHCR images by digest.
- Django runs behind Gunicorn with hardened production settings.
- NGINX owns the public hostname and proxies Django paths privately.
- Migrations and database-aware health checks gate backend activation.
- Current deployments and public smoke checks are healthy.

The main deficiency is documentation drift—not the deployed architecture. Several
documents still describe CI, frontend hosting, PostgreSQL, domain routing, and
security work as planned or Docker Compose-based when those capabilities are
already deployed.

The repository does not yet meet the requested repeatability standard. A new
engineer could understand much of the architecture, but could not safely reproduce
or operate another environment without undocumented Railway/GitHub knowledge,
especially:

- Railway service creation and exact settings
- private GHCR Registry Credentials setup
- project-token/GitHub-secret setup
- domain and DNS setup
- deployment verification
- Railway SSH and first-superuser creation
- credential rotation
- rollback
- backup and restore
- failed-deployment recovery

`BUILD_DEPLOY.md` has also accumulated too many responsibilities. It combines
architecture, current-state evidence, provisioning, CI design, security policy,
release policy, operations, disaster recovery, and unresolved decisions. This
makes it difficult to distinguish executable procedure from commentary.

No files or infrastructure were changed during this audit.

## B. Current architecture as actually implemented

### CURRENT — hosted topology

```text
Browser
  │ HTTPS
  ▼
dev-commerce.empowerment-forge.com
  │
  ▼
Railway frontend service
  │ NGINX :$PORT
  ├── /                 React/Vite production assets + SPA fallback
  ├── /api/             private proxy to Django
  ├── /admin/           private proxy to Django
  └── /static/          private proxy to Django/WhiteNoise
                            │
                            ▼
                    Railway backend service
                    Gunicorn :$PORT
                            │
                            ▼
                          Django
                            │
                    private PostgreSQL
                            │
                    persistent Railway volume
```

Implementation evidence:

- The frontend image uses Node 24 to run tests, lint, and the Vite build, then
  copies only `dist` into NGINX: `frontend/Dockerfile:1`.
- NGINX proxies `/api/`, `/admin/`, and `/static/`, preserving the public host
  and forwarding headers; other routes use SPA fallback:
  `frontend/nginx/default.conf.template:10`.
- The production frontend client defaults to same-origin API requests:
  `frontend/src/api/client.ts:1`.
- The backend image runs `collectstatic`, switches to a non-root user, and starts
  Gunicorn—not `runserver`: `backend/Dockerfile:16`.
- Gunicorn binds to Railway's `PORT`: `backend/gunicorn.conf.py:4`.
- WhiteNoise follows Django's security middleware and uses compressed manifest
  storage: `backend/config/settings.py:157` and
  `backend/config/settings.py:257`.
- Django defines `/health/`, `/admin/`, `/api/auth/`, and catalog routes under
  `/api/`: `backend/config/urls.py:25`.
- The health endpoint actively checks the database and returns 503 when it is
  unreachable: `backend/health/views.py:6`.
- `/api/products/` is the catalog endpoint; no `/api/` index is defined:
  `backend/catalog/urls.py:4`.
- `/api/auth/me/` is a real authentication endpoint:
  `backend/accounts/urls.py:11`.

### CURRENT — security mode

The Railway environment is named `development`, but Django runs in its production
configuration branch. These are deliberately separate concepts.

The code enforces:

- explicit `COMMERCE_ENV`
- a strong `DJANGO_SECRET_KEY`
- `DEBUG=False`
- non-wildcard deployment hosts
- secure session, CSRF, and refresh cookies
- optional trusted forwarded HTTPS
- non-development database credentials

See `backend/config/settings.py:55`.

### CURRENT — CI and immutable deployment

The CI workflow:

1. Builds each image once.
2. Validates that exact image.
3. Scans it with Trivy for fixed HIGH/CRITICAL findings.
4. Saves the validated image as a one-day artifact.
5. On a `develop` push, reloads and pushes that same image to GHCR under the
   commit SHA.
6. Resolves the registry digest.
7. Updates Railway to `image@sha256:digest`.
8. Waits for Railway's terminal deployment status.

Evidence:

- Frontend exact-image validation: `.github/workflows/ci.yml:27`.
- Backend exact-image validation, pytest, Django checks, migration and smoke
  tests: `.github/workflows/ci.yml:125`.
- One-day artifact retention: `.github/workflows/ci.yml:107` and
  `.github/workflows/ci.yml:229`.
- Backend digest deployment: `.github/workflows/ci.yml:287`.
- Frontend digest deployment: `.github/workflows/ci.yml:377`.
- Shared Railway deployment happens only on pushes to `develop`, never
  feature-branch PRs: `.github/workflows/ci.yml:256` and
  `.github/workflows/ci.yml:346`.

A successful `develop` push currently validates and deploys both images, even
when only one side changed. Independent path-based deployment remains a valid
future optimization.

### CURRENT — read-only deployed-state verification

Railway reported:

- Project: `empowerment-forge.com`
- Environment: `development`
- Services: `Postgres`, `backend`, `frontend`
- All three latest deployments: `SUCCESS`
- Postgres volume mounted at `/var/lib/postgresql/data`
- Postgres has a private endpoint and no public domain
- Backend and frontend image auto-update: disabled
- Backend pre-deploy: `python manage.py migrate --noinput`
- Backend health check: `/health/`, 300-second timeout
- Frontend health check: `/`, 300-second timeout
- Backend Registry Credentials: configured, values redacted
- Frontend Registry Credentials: configured, values redacted
- Backend image: digest-qualified GHCR source
- Frontend image: digest-qualified GHCR source
- Frontend variables present: `BACKEND_HOST`, `BACKEND_PORT`
- Required backend variable names are present, including `COMMERCE_ENV`,
  `DJANGO_DEBUG`, database mappings, host/origin settings, and secret-key name

No variable values were requested.

Live read-only verification produced:

- `/`: HTTP 200
- `/api/products/`: HTTP 200
- `/api/`: HTTP 404, correctly reflecting the absence of an API-index route
- `/api/auth/me/`: HTTP 401 without credentials
- `/admin/`: HTTP 302 to the Django admin login
- representative admin CSS: HTTP 200
- public backend `/health/`: HTTP 200 with database status `ok`

The latest `develop` GitHub Actions run for commit `e962519…` completed
successfully.

## C. Documentation that is already accurate

### CURRENT and useful

- `BUILD_DEPLOY.md` correctly explains that Railway's `development` name is
  separate from Django's hardened production security mode:
  `docs/BUILD_DEPLOY.md:36`.
- Its canonical database mapping correctly uses Railway references without
  renaming Postgres variables or copying their values:
  `docs/BUILD_DEPLOY.md:204`.
- Its frontend section correctly describes the Vite build, NGINX runtime,
  same-origin API contract, private backend routing, admin routing, and
  WhiteNoise ownership of Django assets: `docs/BUILD_DEPLOY.md:85`.
- The backend-image section correctly documents Gunicorn and `PORT`:
  `docs/BUILD_DEPLOY.md:116`.
- The GHCR build-once, SHA-tag, digest-resolution, Railway deployment, migration,
  and health-gate description substantially matches CI:
  `docs/BUILD_DEPLOY.md:351`.
- The statement that schema migration and seed/demo data are separate is correct:
  `docs/BUILD_DEPLOY.md:416`.
- The local developer onboarding sequence is generally usable:
  `docs/DEVELOPER_ONBOARDING.md:1`.
- `DOCKER_SETUP.md` has useful local Compose/Podman commands, local variable
  explanations, migrations, tests, and local superuser instructions:
  `docs/DOCKER_SETUP.md:95`.
- `POSTGRES_SETUP.md` is useful for the local Compose database, provided its
  scope is made explicit.
- Authentication documentation contains significant accurate backend detail,
  especially JWT lifetimes, cookie properties, endpoint semantics, and
  logout/blacklisting.
- `ARCHITECTURE_v1.2.md` correctly records Railway as the chosen hosting platform
  and is useful as a historical architecture decision:
  `docs/ARCHITECTURE_v1.2.md:103`.

## D. Inaccurate or stale documentation

### High priority

1. **CURRENT implementation is described as Docker Compose CI.**

   This is false in:

   - `README.md:21`
   - `README.md:96`
   - `docs/DEVELOPER_ONBOARDING.md:81`
   - `docs/DOCKER_SETUP.md:10`
   - `docs/USERAUTH_ARCHITECTURE.md:128`

   CI now builds production images directly and uses controlled container
   targets, not `docker-compose.yml`.

2. **The hosted development environment is repeatedly labeled PLANNED.**

   Examples:

   - `docs/BUILD_DEPLOY.md:36`
   - `docs/BUILD_DEPLOY.md:137`
   - `docs/BUILD_DEPLOY.md:615`
   - `docs/ROADMAP.md:85`

   These are now CURRENT. Remaining backup, rollback, monitoring, promotion, and
   data-bootstrap work should stay explicitly PLANNED or UNKNOWN.

3. **Current component inventory is wrong.**

   `BUILD_DEPLOY.md` says PostgreSQL is local-only and the frontend only has a
   development Dockerfile: `docs/BUILD_DEPLOY.md:65`. Both production images and
   hosted PostgreSQL now exist.

4. **Static-file handling is simultaneously documented as implemented and
   undecided.**

   WhiteNoise and `collectstatic` are correctly described at lines 105–109, but
   static-file handling is called a future decision at
   `docs/BUILD_DEPLOY.md:128`. Compression is already implemented through
   `CompressedManifestStaticFilesStorage`.

5. **DNS and routing remain labeled PLANNED after deployment.**

   `docs/BUILD_DEPLOY.md:301` says final wiring remains to be documented. The
   custom domain and `/api/`, `/admin/`, `/static/` routing are proven. Cloudflare
   proxy mode, DNS ownership procedure, certificate boundary, and HSTS remain
   incomplete or unknown and should be separated from the established routing.

6. **Frontend API configuration is described as undefined.**

   `docs/BUILD_DEPLOY.md:319` says the deployed frontend API contract is not yet
   defined. It is now same-origin by default, with NGINX private proxying.

7. **Backend host/security documentation is incomplete.**

   `docs/BUILD_DEPLOY.md:273` omits `dev-commerce.empowerment-forge.com` from the
   described allowed-host set.

   It also says forwarded HTTPS retains secure redirect behavior, but Railway
   currently defines `DJANGO_SECURE_SSL_REDIRECT` and the documentation does not
   explain its actual deployed setting or why the override is needed. That
   operational exception should be documented precisely without exposing any
   secret.

8. **The backend public hostname wording is stale.**

   It remains deployed, but private frontend-to-backend proxying is now proven.
   `docs/BUILD_DEPLOY.md:291` still frames it as pending initial proxy
   verification.

   **UNKNOWN / REQUIRES DECISION:** remove it now, retain it as a restricted
   operational endpoint, or retain temporarily for another milestone. The audit
   does not recommend silently removing it.

9. **The “Open Decisions” list includes resolved decisions.**

   `docs/BUILD_DEPLOY.md:660` still lists frontend topology, same-origin routing,
   static-file handling, immutable artifact identity, private PostgreSQL
   networking, and image scanning as open. These should be moved to CURRENT
   architecture or implementation records.

10. **Deployment checklist evidence is not maintained.**

    The checklist at `docs/BUILD_DEPLOY.md:628` remains unchecked even for proven
    controls. It should either become a per-environment executable checklist with
    evidence fields or be replaced with explicit CURRENT/UNKNOWN sections.

### Medium priority

11. **README deployment status is materially behind implementation.**

    `README.md:201` calls the deployment guide “intended” Railway guidance. The
    README should provide a short current architecture/status and link to canonical
    provisioning and operations procedures.

12. **UI documentation treats a production frontend as hypothetical.**

    - `docs/UI_SETUP.md:213`
    - `docs/DOCKER_SETUP.md:407`

13. **Roadmap milestones mix completed and incomplete controls without status.**

    `docs/ROADMAP.md:106` combines completed deployment work with unimplemented
    backup, restore, rollback, monitoring, and broader security controls.

14. **Django architecture inventory is incomplete.**

    `docs/DJANGO_ARCHITECTURE.md:28` omits accounts, JWT blacklist, health, and
    WhiteNoise. Its database example also hardcodes port 5432 and frames
    configuration only around Docker, while settings consume `DATABASE_PORT` and
    Railway references.

15. **Frontend auth documents blur target architecture and implemented UI.**

    `docs/FRONTEND_AUTH_PATTERN.md:1` presents future interceptor/storage behavior
    as mandatory current practice, but the frontend currently has only a small
    bearer-capable fetch client and no completed login lifecycle. Label these
    sections PLANNED or “design contract.”

16. **Frozen architecture contains statements superseded by implementation.**

    `ARCHITECTURE_v1.2.md` should remain frozen, but it needs a banner identifying
    its date, historical role, and superseding current-state document. For example,
    its “no custom auth implementation” language no longer describes the current
    JWT endpoints.

17. **`frontend/README.md` is still the generic Vite starter README.**

    It does not explain project scripts, same-origin API behavior, NGINX production
    hosting, or local proxy configuration.

18. **AI-specific operational assumptions appear in durable roadmap/testing
    documents.**

    Examples include Codex/ChatGPT access checks in
    `docs/COMMERCE_ARCHITECT_PUBLIC_ROADMAP.md:445` and Codex-driven test templates
    in `docs/TESTING_STRATEGY.md:183`.

    AI assistance may be mentioned as optional tooling, but it must not be a
    prerequisite or acceptance criterion for environment operation.

## E. Missing human-reproducible procedures

### CURRENT behavior without a complete human procedure

1. **Railway prerequisites and access**

   Missing:

   - required Railway role
   - required GitHub organization/repository permissions
   - required GHCR package permissions
   - required DNS-provider access
   - Railway CLI installation/version/authentication
   - how to select the correct project/environment safely
   - how to confirm no staged Railway changes exist before editing

2. **New-environment provisioning**

   The canonical sequence has good principles but lacks executable detail for:

   - creating `backend` and `frontend`
   - using bootstrap image sources to expose Registry Credentials
   - entering read-only GHCR credentials
   - disabling image auto-update
   - attaching the persistent Postgres volume
   - confirming Postgres has no public TCP domain
   - setting health paths/timeouts/restart policy
   - setting the migration pre-deploy command
   - attaching frontend and temporary backend domains
   - setting service references
   - verifying registry pulls without exposing credentials

3. **Environment parameter manifest**

   There is no concise table identifying what varies by environment:

   - Railway project/environment IDs
   - backend/frontend service IDs
   - domains
   - GHCR namespace
   - region and replica count
   - secret ownership
   - capacity
   - seed/demo-data policy

   The workflow currently hardcodes the development project and service IDs at
   `.github/workflows/ci.yml:303` and `.github/workflows/ci.yml:393`. That works
   for development but is not directly reusable for UAT/production without an
   explicit parameterization or promotion decision.

4. **GitHub setup**

   Missing:

   - create a Railway Project Token scoped to the exact environment
   - add it as repository Actions secret `RAILWAY_TOKEN`
   - configure GHCR package visibility/access
   - explain why `GITHUB_TOKEN` needs only `packages: write` in publish jobs
   - configure branch protection/required `test` check
   - verify feature branches cannot obtain deployment credentials
   - rotate/revoke the Railway token

5. **First superuser**

   Local `createsuperuser` is documented, but hosted bootstrap is not.

   The canonical hosted procedure should document:

   - select project/environment/service
   - open Railway SSH against the deployed backend
   - run `python manage.py createsuperuser` interactively
   - enter credentials only at the terminal prompt
   - verify only active/staff/superuser flags
   - close the session
   - never store the password in docs, shell history, CI, variables, or seeds

6. **End-to-end acceptance**

   There is no single reproducible acceptance checklist covering:

   - Railway statuses
   - frontend root
   - SPA fallback
   - `/api/products/`
   - `/api/auth/me/` expected 401
   - `/api/` expected 404
   - `/admin/` expected redirect
   - admin static asset
   - backend health/database state
   - Postgres private/no-public-domain state
   - deployed digest matches the GHCR digest for the merge SHA

7. **Normal deployment explanation**

   A human-oriented account of automation is missing.

   CURRENT:

   - PRs into `develop`: validate both images; no publish/deploy.
   - pushes to `main`: validate both images; no publish/deploy.
   - merge/push to `develop`: validate both; publish both; deploy both by digest.
   - backend migration runs automatically before backend activation.
   - Railway health checks gate activation.
   - CI waits for Railway terminal status.

   Human responsibilities still include approving/merging changes, investigating
   failures, maintaining credentials, and performing post-deploy application
   checks. Automated rollback and explicit post-deploy public smoke checks are not
   present.

## F. Security/credential documentation gaps

### CURRENT controls

- Secrets are not baked into images.
- CI uses `GITHUB_TOKEN` for GHCR publishing.
- Railway uses separate Registry Credentials for private pulls.
- A scoped `RAILWAY_TOKEN` is referenced only by deployment jobs.
- Database values are referenced rather than copied.
- Registry credentials exist on both Railway services, with values redacted.
- `DJANGO_SECRET_KEY` exists as a Railway variable name; no value was read.

### Missing documentation

A credential inventory should document owner, location, purpose, minimum scope,
rotation trigger, rotation procedure, verification, and revocation for:

| Credential | Safe documented location | Required scope |
|---|---|---|
| `RAILWAY_TOKEN` | GitHub Actions repository secret | Project/environment deployment scope only |
| GHCR pull PAT | Railway Registry Credentials on backend and frontend | `read:packages`; no repository write permission |
| `DJANGO_SECRET_KEY` | Railway backend service variable | Environment-unique; never copied |
| PostgreSQL password | Railway-managed Postgres variables | Referenced from backend; never copied |
| DNS credentials | DNS provider, outside repository | Minimum permissions for required records |
| Superuser password | Human-controlled password manager | Never a Railway variable, seed, fixture, or CI secret |

Additional gaps:

- no GHCR credential-rotation runbook
- no Railway Project Token rotation runbook
- no `DJANGO_SECRET_KEY` rotation impact analysis
- no database-password rotation procedure
- no documented emergency credential revocation path
- no operator-access review or offboarding procedure
- no warning that changing `DJANGO_SECRET_KEY` invalidates signed sessions/tokens
  and may affect application state
- no audit procedure to verify values are configured without printing them
- no Railway SSH safety guidance
- no clear division between secrets supplied by Railway and references consumed by
  Django

**RECOMMENDED:** documentation should show variable names and reference expressions
only. It should never include screenshots or command output containing rendered
values.

## G. Operational/runbook gaps

### Missing or inadequate procedures

1. **Deployment status**

   No canonical command/dashboard sequence for identifying the deployment
   belonging to a commit/digest and waiting for terminal status.

2. **Logs**

   No instructions distinguishing build, pre-deploy/migration, deploy/runtime,
   and HTTP proxy logs, or how to avoid exposing secrets while sharing logs.

3. **Railway SSH**

   No hosted backend SSH procedure, environment-selection safeguards, or list of
   permitted operational commands.

4. **Migration verification**

   CI proves migrations in a disposable test database and Railway runs them, but
   operators lack a runbook for:

   - identifying the pre-deploy migration result
   - `showmigrations`
   - handling a failed migration
   - forward-fix versus rollback decisions
   - preventing accidental concurrent/manual migration execution

5. **Superuser administration**

   Missing:

   - first creation
   - privilege verification
   - password reset
   - disabling/removing a compromised admin
   - periodic privileged-account review

6. **Health verification**

   Health behavior is described, but not packaged as a post-deploy checklist with
   expected codes and meanings. In particular:

   - `/api/` 404 is valid
   - `/api/auth/me/` 401 without credentials is valid
   - `/admin/` 302 is expected when unauthenticated

7. **Rollback**

   `BUILD_DEPLOY.md` describes principles but no executable application rollback
   procedure. It also does not define:

   - who authorizes rollback
   - how to select a prior known-good digest
   - how CI/Railway drift is prevented afterward
   - how migrations constrain rollback
   - verification after rollback

8. **Database backup/restore**

   This is the most consequential gap because the hosted database is persistent
   and must not be treated as disposable.

   **UNKNOWN / REQUIRES DECISION:**

   - Railway backup/PITR capability for the current plan
   - retention
   - recovery point and recovery time objectives
   - export mechanism
   - encrypted storage
   - isolated restore target
   - restore drill frequency
   - destructive-operation backup requirements
   - who may restore production-like data

9. **Failed deployment recovery**

   Missing branching procedure for:

   - GHCR push failure
   - registry pull failure
   - migration failure
   - healthcheck failure
   - NGINX proxy/DNS failure
   - application crash
   - database outage
   - Railway API/CLI failure
   - previous deployment remains active versus no healthy deployment

10. **Monitoring and incident response**

    No alert ownership, notification channel, response time, incident
    classification, or service-level targets are defined.

11. **Capacity and regions**

    The actual services currently run one replica in Railway's `ams` region, but
    capacity and geographic placement are undocumented. This should be an
    environment parameter, not an accidental default.

12. **Backend public domain**

    **UNKNOWN / REQUIRES DECISION:** because the frontend private proxy is now
    verified, the direct backend domain can technically be reconsidered. Removing
    it would better match the target architecture, but health, emergency access,
    and operational requirements must be evaluated first.

## H. Recommended documentation structure

Yes—`BUILD_DEPLOY.md` has too many responsibilities.

### RECOMMENDED structure

#### `docs/BUILD_DEPLOY.md`

Keep this as the concise build and normal-deployment contract:

- artifact definitions
- Dockerfiles and startup commands
- CI trigger matrix
- exact-image validation
- GHCR naming/tag/digest flow
- Railway deploy control plane
- migration and health-gate behavior
- normal deployment verification
- future path-based deployment optimization

Avoid putting first-time provisioning, credential rotation, rollback, or backup
procedures here.

#### `docs/ENVIRONMENT_PROVISIONING.md`

Create an environment-independent bootstrap procedure:

- prerequisites and permissions
- parameter table
- Railway project/environment creation
- Postgres provisioning and persistence
- backend/frontend service creation
- private Registry Credentials
- variables and references
- domains/DNS
- health checks and pre-deploy migration
- first deployment
- first interactive superuser
- full acceptance checklist
- explicit no-seed boundary

The procedure should be structurally identical for development, implementation,
UAT, and production.

#### `docs/OPERATIONS.md`

Create the human runbook:

- service and deployment status
- logs
- SSH
- health tests
- migration inspection
- superuser administration
- secret and registry-credential rotation
- rollback
- backup/restore
- failed-deployment diagnosis
- incidents and access review

#### `docs/ARCHITECTURE.md`

Recommended as a concise current hosted architecture document, or incorporate the
same information into `BUILD_DEPLOY.md` if avoiding another file is preferred.
Keep `ARCHITECTURE_v1.2.md` as a clearly labeled historical/frozen decision
record.

#### `docs/DECISIONS.md` or ADRs

Optional but valuable for durable decisions:

- Railway selection
- production-like security mode in non-production
- NGINX same-origin/private proxy
- digest deployments controlled by GitHub Actions
- WhiteNoise ownership of Django static assets
- no automatic seed or privileged-user creation

## I. Exact file recommendations

### Create

1. `docs/ENVIRONMENT_PROVISIONING.md`
2. `docs/OPERATIONS.md`
3. `docs/ARCHITECTURE.md` — recommended if a short canonical current-state
   document is desired
4. Optional `docs/adr/` records for durable deployment decisions

### Modify

1. `README.md`
   - current hosted status
   - correct CI description
   - concise architecture
   - updated documentation map

2. `docs/BUILD_DEPLOY.md`
   - remove completed work from PLANNED sections
   - retain build/deploy contract
   - move provisioning and operations material
   - document actual trigger matrix
   - document current allowed-host/SSL-redirect behavior
   - remove resolved open decisions

3. `docs/DEVELOPER_ONBOARDING.md`
   - correct CI description
   - clearly separate local development from hosted operation

4. `docs/DOCKER_SETUP.md`
   - declare local-only scope
   - remove “future production frontend/managed Postgres” wording
   - link to hosted provisioning

5. `docs/UI_SETUP.md`
   - replace hypothetical production hosting wording
   - document same-origin API behavior at a high level

6. `docs/ROADMAP.md`
   - mark deployment milestone complete
   - retain rollback, backup, restore, monitoring, and promotion as incomplete
   - identify documentation remediation as the next operational-readiness milestone

7. `docs/DJANGO_ARCHITECTURE.md`
   - update installed components, environment contract, database port, health,
     JWT, and WhiteNoise

8. `docs/USERAUTH_ARCHITECTURE.md`
   - correct CI description
   - update same-origin hosting from expected to current
   - distinguish implemented backend from planned frontend login experience

9. `docs/FRONTEND_AUTH_PATTERN.md`
   - label unimplemented UI behavior as PLANNED/design contract

10. `docs/POSTGRES_SETUP.md`
    - explicitly label it local-only
    - link hosted database provisioning and operations

11. `docs/DEVOPS.md`
    - add branch-to-CI/deployment consequences or link the canonical deploy guide

12. `frontend/README.md`
    - replace generic Vite starter content with project-specific usage

13. `docs/TESTING_STRATEGY.md`
    - make AI-generated tests optional
    - document current container-image validation and Trivy gates

14. `SECURITY.md`
    - add operational security-reporting and secret-exposure response links if not
      already covered

### Retain but annotate

- `docs/ARCHITECTURE_v1.2.md`: retain as frozen historical record; add a
  supersession banner.
- `docs/COMMERCE_ARCHITECT_PUBLIC_ROADMAP.md`: retain as historical/public-
  governance roadmap, but remove AI access as an operational dependency and mark
  completed security/deployment work accurately.

### Retire or consolidate

No file must be deleted immediately. After the new structure exists:

- consolidate duplicated deployment material from `DOCKER_SETUP.md`,
  `UI_SETUP.md`, `USERAUTH_ARCHITECTURE.md`, and `BUILD_DEPLOY.md`
- replace duplicate procedures with links to one canonical owner
- archive obsolete roadmap/checklist portions rather than letting contradictory
  instructions remain active

## J. Prioritized remediation plan

### P0 — factual safety

1. Correct all “Docker Compose CI” claims.
2. Mark hosted development, images, Railway Postgres, domain, proxy, admin/static
   routing, migrations, health checks, and digest deployment as CURRENT.
3. Correct backend host/forwarded-HTTPS/secure-redirect documentation.
4. State clearly that hosted Postgres is persistent application storage, not
   disposable local data.
5. Preserve the explicit prohibition on documenting superuser credentials.

### P1 — reproducible bootstrap

6. Create `ENVIRONMENT_PROVISIONING.md`.
7. Add a parameter manifest separating invariant steps from environment-specific
   values.
8. Document GHCR Registry Credentials, `RAILWAY_TOKEN`, Railway references,
   domains, health checks, migrations, and first-superuser creation.
9. Add a complete clean-environment acceptance checklist.
10. State explicitly that no canonical catalog/demo seed procedure exists.

### P1 — operational readiness

11. Create `OPERATIONS.md`.
12. Document status, logs, SSH, health, migration verification, and superuser
    administration.
13. Define application rollback to a prior digest.
14. Decide and test backup/restore before treating the environment as
    operationally recoverable.
15. Document credential rotation and failed-deployment recovery.

### P2 — information architecture

16. Reduce `BUILD_DEPLOY.md` to the normal build/deploy contract.
17. Add or designate a canonical current architecture document.
18. Annotate historical/frozen architecture documents.
19. Make README and onboarding documents route readers to the correct canonical
    procedures.
20. Separate implemented authentication behavior from planned UI patterns.

### P2 — automation portability

21. Decide how environment-specific Railway project/service IDs should be supplied
    for implementation, UAT, and production.
22. Decide promotion/approval mechanics for environments other than development.
23. Consider path-based independent frontend/backend builds only after
    documentation and recovery procedures are complete.

### P3 — unresolved operational governance

24. Define alerting and incident ownership.
25. Define capacity, region, recovery objectives, retention, and access reviews.
26. Decide whether to remove the temporary public backend domain.
27. Decide CSP/HSTS and Cloudflare/Railway TLS ownership.
28. Decide the catalog/bootstrap-data strategy separately from migrations.

## K. Definition of Done for documentation/reproducibility

Documentation remediation is complete when a competent engineer can, using only
repository documentation and authorized service access:

- identify CURRENT, PLANNED, RECOMMENDED, and UNKNOWN behavior without
  contradiction
- install the documented prerequisite tooling
- create a Railway project and named environment
- provision persistent, private Railway PostgreSQL
- create exactly one backend and one frontend service
- configure private GHCR authentication without exposing credentials
- configure all Django and NGINX variables using Railway references where
  appropriate
- configure health checks, pre-deploy migrations, restart behavior, and image
  auto-update policy
- configure public domains and DNS
- configure the scoped GitHub `RAILWAY_TOKEN`
- explain and verify the build-once → validate → scan → SHA tag → digest → Railway
  flow
- predict exactly what PR, `develop`, and `main` workflow events do
- deploy an equivalent environment without AI assistance
- prove `/`, SPA fallback, `/api/products/`, `/api/auth/me/`, `/api/`, `/admin/`,
  `/static/`, and `/health/` behave as documented
- identify the deployed Git commit, GHCR digest, and Railway deployment
- use Railway SSH safely
- create the first superuser interactively without recording its password
- inspect migration status
- rotate every documented credential safely
- roll back an application image
- restore a database backup into an isolated target and verify it
- diagnose common deployment failures
- distinguish persistent hosted data from disposable local data
- understand that migrations create/evolve schema but never imply seed/demo data
- understand that no canonical catalog/demo seed strategy has been approved
- understand that privileged-user creation remains an explicit secure human
  operation
- reproduce implementation, UAT, or production through the same structural
  sequence with only documented parameter changes

Until rollback and database restore have executable, tested procedures, the
environment is successfully deployed but not fully operationally reproducible.
