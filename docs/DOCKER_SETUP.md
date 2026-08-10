# Container Setup & Configuration

## Purpose

This document explains how to run the Commerce Architect PostgreSQL, Django, and
React/Vite development services locally with either Podman Compose or Docker
Compose. The checked-in `docker-compose.yml` is compatible with both workflows;
use the container runtime that fits your development environment.

GitHub Actions CI currently uses Docker Compose. Local Linux development can use
Podman and Podman Compose without changing the Compose file.

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
| Run backend tests | `podman-compose exec -T web pytest` | `docker compose exec -T web pytest` |
| Run frontend tests | `podman-compose exec -T frontend npm run test -- --run` | `docker compose exec -T frontend npm run test -- --run` |
| Build the frontend | `podman-compose exec -T frontend npm run build` | `docker compose exec -T frontend npm run build` |
| Lint the frontend | `podman-compose exec -T frontend npm run lint` | `docker compose exec -T frontend npm run lint` |
| Apply Django migrations | `podman-compose exec web python manage.py migrate` | `docker compose exec web python manage.py migrate` |
| Open the Django shell | `podman-compose exec web python manage.py shell` | `docker compose exec web python manage.py shell` |
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
podman-compose exec web python manage.py migrate
```

With Docker Compose:

```bash
docker compose exec web python manage.py migrate
```

When intentionally changing Django models, generate migration files with the
corresponding runtime command:

```bash
podman-compose exec web python manage.py makemigrations
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
podman-compose exec web python manage.py createsuperuser
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
podman-compose exec db psql -U commerce -d commerce_db
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
    `/api` proxy to Django over the Compose network. Native host Vite development
    still defaults to `http://localhost:8000` when that variable is unset.
-   PostgreSQL listens on port `5432` and persists data in `postgres_data`.
-   `DATABASE_HOST=db` is correct inside the Compose network; it should not be
    replaced with `localhost` in the container configuration.
-   Rebuild the Django image when `backend/Dockerfile` or Python dependency
    inputs in `backend/` change.
-   Rebuild the frontend image when `frontend/Dockerfile.dev` changes. Frontend
    dependency changes are synchronized from `frontend/package-lock.json` by
    `npm ci` at container startup. Restarting `frontend` is sufficient after a
    lockfile change; deleting `frontend_node_modules` is not normally necessary.
-   This container runs the Vite development server only. A future production
    deployment may build the React application and publish its static assets to
    dedicated frontend or static hosting instead. Likewise, local containerized
    PostgreSQL does not require production to use a PostgreSQL container; a
    managed PostgreSQL service remains a valid future choice. Production hosting
    is intentionally undecided.
-   GitHub Actions runs frontend tests with its Node 24 setup, then builds and
    starts only `web` and `db` for backend tests. It does not duplicate frontend
    dependency installation or tests in the Compose frontend service.
