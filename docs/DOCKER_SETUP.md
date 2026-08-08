# Container Setup & Configuration

## Purpose

This document explains how to run the Commerce Architect Django and PostgreSQL
services locally with either Podman Compose or Docker Compose. The checked-in
`docker-compose.yml` is compatible with both workflows; use the container runtime
that fits your development environment.

GitHub Actions CI currently uses Docker Compose. Local Linux development can use
Podman and Podman Compose without changing the Compose file.

------------------------------------------------------------------------

# Architecture Overview

The Compose project defines two services:

-   `web` -- Django development server, published at local port `8000`
-   `db` -- PostgreSQL 16, published at local port `5432`

The named volume `postgres_data` stores PostgreSQL data outside the lifecycle of
an individual container. A normal stop and restart therefore preserves database
data.

Compose creates an internal network for the services. Django connects to
PostgreSQL with `DATABASE_HOST=db`; `db` is the Compose service name and resolves
inside that network. Local application access uses `http://localhost:8000/`.

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

Both local approaches run the same `web` and `db` service definitions.

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

`up` creates and starts the services. `--build` builds the Django image before
starting it, and `-d` leaves both services running in the background. The command
also pulls PostgreSQL 16 when needed, creates the internal network, and creates or
reuses the `postgres_data` volume.

Open the backend at:

```text
http://localhost:8000/
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

Expect both `web` and `db` to be running. If `db` is unavailable, Django cannot
connect to PostgreSQL. If `web` is unavailable, the backend and proxied frontend
API requests cannot reach port 8000.

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
-   PostgreSQL listens on port `5432` and persists data in `postgres_data`.
-   `DATABASE_HOST=db` is correct inside the Compose network; it should not be
    replaced with `localhost` in the container configuration.
-   Rebuild the Django image when its Dockerfile or Python dependency inputs
    change.
-   GitHub Actions uses `docker compose build`, `docker compose up -d`, and
    `docker compose exec -T web pytest`, then tears the services down.
