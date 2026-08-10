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

Compose creates an internal network for the services. Django connects to
PostgreSQL with `DATABASE_HOST=db`, and Vite proxies `/api` requests to
`http://web:8000`; `db` and `web` are Compose service names that resolve inside
that network. Host access uses `http://localhost:8000/` for Django and
`http://localhost:5173/` for React/Vite.

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

To view service output, use `podman-compose logs` or `docker compose logs` and
optionally name a service, such as `web`.

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

# Stop Containers

With Podman Compose:

```bash
podman-compose down
```

With Docker Compose:

```bash
docker compose down
```

`down` stops and removes the project containers and network while preserving the
named PostgreSQL volume.

------------------------------------------------------------------------

# Full Reset (Destructive)

Warning: adding `-v` deletes the named PostgreSQL volume and all local database
data. Use this only when a complete database reset is intentional.

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
-   Rebuild the Django image when its Dockerfile or Python dependency inputs
    change.
-   Rebuild the frontend image when `frontend/Dockerfile.dev` changes. Frontend
    dependency changes are synchronized from the lockfile by `npm ci` at
    container startup.
-   This container runs the Vite development server only. A future production
    deployment may build the React application and publish its static assets to
    dedicated frontend hosting instead.
-   GitHub Actions runs frontend tests with its Node 24 setup, then builds and
    starts only `web` and `db` for backend tests. It does not duplicate frontend
    dependency installation or tests in the Compose frontend service.
