# Container Setup & Configuration

## Purpose

This **local-development-only** document explains how to run the Commerce Architect PostgreSQL, Django, and
React/Vite development services locally with either Podman Compose or Docker
Compose. The checked-in `docker-compose.yml` is compatible with both workflows;
use the container runtime that fits your development environment.

Hosted environments and CI do not use this Compose topology. See
[BUILD_DEPLOY.md](BUILD_DEPLOY.md). Local Linux development can use Podman and
Podman Compose without changing the Compose file.

------------------------------------------------------------------------

# Architecture Overview

The Compose project defines three services:

-   `web` -- Django development server, published at local port `8000`
-   `db` -- PostgreSQL 16, published at local port `5432`
-   `frontend` -- React/Vite development server, published at local port `5173`

The named volume `postgres_data` stores PostgreSQL data outside the lifecycle of
an individual container. A normal stop and restart therefore preserves database
data. The named volume `frontend_node_modules` keeps Linux frontend dependencies
inside the container environment while `./frontend` is bind-mounted at `/app`
for live source edits. At startup, `npm ci` synchronizes that dependency volume
with the checked-in `frontend/package-lock.json`; host `node_modules` does not
replace the container dependencies.

The Django image is built from `./backend`, and that directory is bind-mounted
at `/app` in the `web` container. The React/Vite image and bind mount continue to
use `./frontend`. Compose orchestration remains in `docker-compose.yml` at the
repository root.

Compose creates an internal network for the services. Django connects to
PostgreSQL with `DATABASE_HOST=db`, and Vite proxies `/api` requests to
`http://web:8000`; `db` and `web` are Compose service names that resolve inside
that network. Host access uses `http://localhost:8000/` for Django and
`http://localhost:5173/` for React/Vite.

```text
Host browser                         Compose network

localhost:5173 -> React/Vite         frontend -> http://web:8000 -> Django
localhost:8000 -> Django             Django   -> db             -> PostgreSQL
```

`web:8000` is internal Compose service addressing. It does not conflict with
`localhost:8000`, which is the published host port used by a browser or other
host tool. When Vite runs in Compose, it accepts the browser's `/api` request on
port 5173 and forwards that request to Django at `web:8000`.

------------------------------------------------------------------------

# Choose a Local Runtime

## Linux / Pop!_OS / Podman

Install Podman and Podman Compose using the package-management approach for your
Linux distribution. Verify both commands are available:

```bash
podman --version
podman-compose --version
```

The Compose file uses OCI-compatible images and works with Podman Compose.

### Podman command convention

Use `podman-compose` for application lifecycle and orchestration (`up`, `start`,
`stop`, `down`, `ps`, and `logs`). Use direct `podman exec` commands to run
tools inside the deliberately named running containers: `commerce_web`,
`commerce_db`, and `commerce_frontend`.

Do not use `podman-compose exec`. Older wrappers may echo a generated command
containing expanded environment values; direct `podman exec` uses the existing
container and avoids that project-observed disclosure path. The ignored `.env`
file remains the supported location for local secret overrides. Never print a
resolved container environment while handling real credentials.

## Windows / WSL2 / Docker Desktop

Install Docker Desktop, enable WSL2 integration for the distribution containing
the repository, and verify Docker from the WSL shell:

```bash
docker version
docker compose version
```

Both local approaches run the same `db`, `web`, and `frontend` service
definitions.

------------------------------------------------------------------------

# First Build and Start

Run Compose commands from the repository root.

With Podman Compose:

```bash
podman-compose up --build -d
```

With Docker Compose:

```bash
docker compose up --build -d
```

`up` creates and starts the services. `--build` builds the Django and frontend
development images, and `-d` leaves all three services running in the
background. The command also pulls PostgreSQL 16 when needed, creates the
internal network, and creates or reuses the named volumes.

Open the applications at:

```text
React/Vite: http://localhost:5173/
Django:     http://localhost:8000/
```

The checked-in Compose file is explicitly development-only. It selects
`COMMERCE_ENV=development` and passes a labeled non-secret Django key and fixed
local PostgreSQL credentials. Production deployments must inject their own
configuration and must not reuse these values.

------------------------------------------------------------------------

# Environment and Production Security

`.env.example` contains safe local examples and may be copied to `.env` for
local overrides. `.env` and secret-bearing variants are ignored by Git;
`.env.example` remains tracked. Compose works without either file.

Compose substitutions such as `${VARIABLE:-default}` use the environment value
when it is set and non-empty; otherwise, Compose uses the displayed fallback.
The checked-in fallback values are development-only and must not be reused in
production.

## Core Django Variables

| Variable | Development | Production |
| --- | --- | --- |
| `COMMERCE_ENV` | `development` | Required: `production` |
| `DJANGO_SECRET_KEY` | Labeled local-only value | Required strong secret; no fallback or automatic generation |
| `DJANGO_DEBUG` | Defaults to `true` | Must be omitted/false; true is rejected |
| `DJANGO_ALLOWED_HOSTS` | Localhost, loopback, and Compose/test hosts | Required comma-separated deployment hostnames |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Empty for the same-origin Vite proxy | Comma-separated HTTPS origins when trusted cross-origin POSTs are required |
| `DATABASE_HOST` | `db` through Compose | Required |
| `DATABASE_NAME` | Derived from `POSTGRES_DB` | Required |
| `DATABASE_USER` | Derived from `POSTGRES_USER` | Required |
| `DATABASE_PASSWORD` | Fixed local-only value | Required; known development values are rejected |
| `DATABASE_PORT` | `5432` | Optional; defaults to `5432` |
| `AUTH_REQUIRE_VERIFIED_EMAIL` | `true` in Compose to exercise the full flow | Explicit policy; defaults to `false` outside Compose for existing-account compatibility |
| `AUTH_EMAIL_VERIFICATION_TTL_SECONDS` | `86400` | Positive token lifetime |
| `AUTH_EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS` | `60` | Non-negative resend cooldown |
| `AUTH_PASSWORD_RECOVERY_TTL_SECONDS` | `1800` | Positive recovery-token lifetime |
| `AUTH_PASSWORD_RECOVERY_RESEND_COOLDOWN_SECONDS` | `60` | Non-negative per-account recovery cooldown |
| `AUTH_FRONTEND_BASE_URL` | `http://localhost:5173` | Required absolute HTTPS URL in production |
| `EMAIL_BACKEND` | First-party readable console backend | Required delivery-capable backend in production |
| `DEFAULT_FROM_EMAIL` | Local non-delivery sender | Required non-local sender in production |
| `SMTP_HOST` | Unused by console mode | Required when SMTP is selected |
| `SMTP_PORT` | `587` | Integer from 1 through 65535 |
| `SMTP_USERNAME` | Unused by console mode | Required when SMTP is selected |
| `SMTP_PASSWORD` | Unused by console mode | Required secret when SMTP is selected |
| `SMTP_USE_TLS` | `true` | Explicit TLS; mutually exclusive with SSL |
| `SMTP_USE_SSL` | `false` | Implicit TLS; mutually exclusive with TLS |
| `SMTP_TIMEOUT` | `10` | Positive timeout in seconds |

Production fails startup if its Django secret is absent, shorter than 50
characters, begins with `django-insecure-`, or contains `changeme`. It also
fails if debug is enabled, deployment hosts are absent, only development hosts
are supplied, database settings are missing, or a known development database
password is reused.

### Local email modes

The default local console mode requires no external provider. Keep
`EMAIL_BACKEND=accounts.mail.ReadableConsoleEmailBackend`; the first-party
backend prints the plain message body without MIME transfer encoding. Follow
the `web` logs after registration:

```bash
podman-compose logs -f web
# or: docker compose logs -f web
```

Open the printed `http://localhost:5173/verify-email?...` link in the browser.
No external email provider is needed.

For real SMTP UAT, copy `.env.example` to the ignored `.env`, select
`django.core.mail.backends.smtp.EmailBackend`, and set the standard `SMTP_*`
variables plus the verified `DEFAULT_FROM_EMAIL`. The application has no
provider SDK dependency. Put the actual SMTP password only in `.env`, then
restart the web service. TLS and SSL cannot both be enabled.

Production rejects missing/insecure frontend URL, console/dummy/in-memory email
backends, a local sender, incomplete SMTP credentials, and invalid SMTP options.
Password recovery reuses the same mailer and frontend base URL; no additional
provider credential or SDK is required.

## HTTPS and Proxy Variables

| Variable | Production behavior |
| --- | --- |
| `DJANGO_SECURE_SSL_REDIRECT` | Defaults to `true`; set false only when an explicitly reviewed upstream performs the redirect |
| `DJANGO_TRUST_FORWARDED_PROTO` | Set true only behind a trusted proxy that overwrites `X-Forwarded-Proto` |
| `DJANGO_SECURE_HSTS_SECONDS` | Defaults to `0` until the production domain and HTTPS behavior are verified |
| `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS` | Defaults to `false`; enable only after all subdomains are HTTPS-ready |
| `DJANGO_SECURE_HSTS_PRELOAD` | Defaults to `false`; preload is intentionally deferred |

Production always sets Django session, CSRF, and refresh-token cookies to
`Secure`. The refresh token remains `HttpOnly`, `SameSite=Strict`, and scoped to
`/api/auth/`. Development uses a non-`Secure` refresh cookie so authentication
can work over local HTTP; `HttpOnly`, `SameSite`, and path restrictions remain
unchanged.

The current Vite development server proxies `/api` to `http://web:8000`, so the
browser makes same-origin requests and no CORS package or wildcard policy is
needed. The initial production assumption is likewise same-origin browser/API
routing through a trusted HTTPS proxy. A separate browser origin requires a
deliberate CORS and CSRF review; `SameSite=None` is not a default.

Run the ordinary and deployment-oriented Django checks with:

```bash
podman exec -i commerce_web python manage.py check
podman exec -i commerce_web python manage.py check --deploy
```

Docker users may instead run `docker compose exec -T web` followed by the same
command. The deployment check must also run in the real production environment
so it evaluates production variables rather than the intentionally relaxed
development values.

------------------------------------------------------------------------

# Check Service Status

With Podman Compose:

```bash
podman-compose ps
```

With Docker Compose:

```bash
docker compose ps
```

Expect `db`, `web`, and `frontend` to be running. If `db` is unavailable, Django
cannot connect to PostgreSQL. If `web` is unavailable, the backend and proxied
frontend API requests cannot reach port 8000. If `frontend` is unavailable, the
Vite development UI cannot be reached on port 5173.

The developer command quick reference below includes commands for all logs and
individual service logs.

------------------------------------------------------------------------

# Developer Command Quick Reference

Run these commands from the repository root. Use the command column for the
runtime selected during onboarding.

| Operation | Podman Compose | Docker Compose |
| --- | --- | --- |
| Build and start the complete stack | `podman-compose up --build -d` | `docker compose up --build -d` |
| Start existing containers | `podman-compose start` | `docker compose start` |
| Stop containers without removing them | `podman-compose stop` | `docker compose stop` |
| Stop and remove containers and the network | `podman-compose down` | `docker compose down` |
| Show service status | `podman-compose ps` | `docker compose ps` |
| Follow all logs | `podman-compose logs -f` | `docker compose logs -f` |
| Follow Django logs | `podman-compose logs -f web` | `docker compose logs -f web` |
| Follow frontend logs | `podman-compose logs -f frontend` | `docker compose logs -f frontend` |
| Run backend tests | `podman exec -i commerce_web pytest` | `docker compose exec -T web pytest` |
| Run Django checks | `podman exec -i commerce_web python manage.py check` | `docker compose exec -T web python manage.py check` |
| Check migration consistency | `podman exec -i commerce_web python manage.py makemigrations --check --dry-run` | `docker compose exec -T web python manage.py makemigrations --check --dry-run` |
| Run frontend tests | `podman exec -i commerce_frontend npm run test -- --run` | `docker compose exec -T frontend npm run test -- --run` |
| Build the frontend | `podman exec -i commerce_frontend npm run build` | `docker compose exec -T frontend npm run build` |
| Lint the frontend | `podman exec -i commerce_frontend npm run lint` | `docker compose exec -T frontend npm run lint` |
| Apply Django migrations | `podman exec -it commerce_web python manage.py migrate` | `docker compose exec web python manage.py migrate` |
| Open the Django shell | `podman exec -it commerce_web python manage.py shell` | `docker compose exec web python manage.py shell` |
| Synchronize changed frontend dependencies | `podman-compose restart frontend` | `docker compose restart frontend` |

After `backend/Dockerfile`, a Compose service, or another image-build change,
rebuild and
recreate the stack with `podman-compose down` followed by
`podman-compose up --build -d`, or the equivalent Docker Compose commands. A
normal source-code edit does not require a rebuild because the backend and
frontend source directories are bind-mounted. A frontend lockfile change
requires only a frontend restart; startup `npm ci` synchronizes the dependency
volume.

------------------------------------------------------------------------

# Migration Workflow

Apply checked-in migrations after the first start and whenever new migrations
are added.

With Podman Compose:

```bash
podman exec -it commerce_web python manage.py migrate
```

With Docker Compose:

```bash
docker compose exec web python manage.py migrate
```

When intentionally changing Django models, generate migration files with the
corresponding runtime command:

```bash
podman exec -it commerce_web python manage.py makemigrations
```

or:

```bash
docker compose exec web python manage.py makemigrations
```

`makemigrations` creates migration instructions from model changes; `migrate`
applies checked-in migration instructions to PostgreSQL.

------------------------------------------------------------------------

# Create an Admin User

With Podman Compose:

```bash
podman exec -it commerce_web python manage.py createsuperuser
```

With Docker Compose:

```bash
docker compose exec web python manage.py createsuperuser
```

Follow the interactive prompts, then open:

```text
http://localhost:8000/admin/
```

------------------------------------------------------------------------

# Access PostgreSQL

With Podman Compose:

```bash
podman exec -it commerce_db psql -U commerce -d commerce_db
```

With Docker Compose:

```bash
docker compose exec db psql -U commerce -d commerce_db
```

Useful `psql` commands include:

```text
\dt
\d tablename
\q
```

`\dt` lists tables, `\d tablename` describes a table, and `\q` exits the shell.

------------------------------------------------------------------------

# Stop and Remove Containers

`stop` stops the project containers but keeps them available for a later
`start`. It does not remove containers, the Compose network, or named volumes:

```bash
podman-compose stop
```

or:

```bash
docker compose stop
```

`down` stops and removes the project containers and Compose network. It preserves
named volumes when `-v` is omitted:

With Podman Compose:

```bash
podman-compose down
```

With Docker Compose:

```bash
docker compose down
```

Normal shutdown should use `stop` or `down` without `-v`. Both preserve the
PostgreSQL data volume and frontend dependency volume.

`postgres_data` is a Compose-managed named volume, not a fixed repository or
host filesystem path. Its physical location depends on the container runtime
and operating system. Inspect it through `docker volume ls` and
`docker volume inspect`, or `podman volume ls` and `podman volume inspect`,
rather than depending on an underlying host path.

------------------------------------------------------------------------

# Full Volume Reset (Destructive)

**Warning:** `down -v` stops and removes the containers and network **and deletes
the project's named volumes**. This destroys the PostgreSQL development data in
`postgres_data` as well as the replaceable frontend dependency volume. It is not
a normal shutdown command. Use it only when a complete local data reset is
intentional.

With Podman Compose:

```bash
podman-compose down -v
podman-compose up --build -d
```

With Docker Compose:

```bash
docker compose down -v
docker compose up --build -d
```

After resetting the volume, apply migrations again before using the application.

------------------------------------------------------------------------

# Development Notes

-   Django listens on `0.0.0.0:8000` in the `web` container.
-   Vite listens on `0.0.0.0:5173` in the `frontend` container. The frontend
    source bind mount lets Vite observe host edits and provide hot module
    replacement without rebuilding the image.
-   Inside Compose, `VITE_API_PROXY_TARGET=http://web:8000` directs Vite's
    `/api`, `/admin`, and `/static` proxies to Django over the Compose network.
    Native host Vite development still defaults to `http://localhost:8000` when
    that variable is unset.
-   PostgreSQL listens on port `5432` and persists data in `postgres_data`.
-   `DATABASE_HOST=db` is correct inside the Compose network; it should not be
    replaced with `localhost` in the container configuration.
-   Rebuild the Django image when `backend/Dockerfile` or Python dependency
    inputs in `backend/` change.
-   Rebuild the frontend image when `frontend/Dockerfile.dev` changes. Frontend
    dependency changes are synchronized from `frontend/package-lock.json` by
    `npm ci` at container startup. Restarting `frontend` is sufficient after a
    lockfile change; deleting `frontend_node_modules` is not normally necessary.
-   This container runs the Vite development server only. Hosted environments
    use the production frontend image, NGINX, and persistent PostgreSQL as
    documented in [ARCHITECTURE.md](ARCHITECTURE.md). Local volumes and database
    credentials never transfer to hosted environments.
-   GitHub Actions validates the production frontend and backend images directly;
    this Compose frontend remains a local developer convenience.
