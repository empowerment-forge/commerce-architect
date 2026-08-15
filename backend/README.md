# Commerce Architect Backend

The backend is the Django and Django REST Framework API for Commerce Architect.
It uses PostgreSQL for application state and keeps authentication separate from
commerce domains.

The main apps are `accounts` for authentication, `catalog` for product-domain
behavior, and `health` for database-aware readiness. Project configuration lives
in `config`.

## Local commands

Run the full local stack from the repository root, then use the backend service:

```bash
docker compose up --build -d
docker compose exec -T web pytest
docker compose exec -T web python manage.py check
docker compose exec -T web python manage.py migrate
```

Use `podman-compose` in place of `docker compose` for the supported Podman
workflow.

Django migrations live within each app's `migrations/` directory. Migration
files are reviewed schema changes; they do not seed application data or create
privileged users.

The API uses serializers as its transport boundary and keeps views thin;
business rules belong in models or domain services. PostgreSQL schema changes
are expressed through reviewed migrations.

For deeper detail, see the [current architecture](../docs/ARCHITECTURE.md),
[container setup](../docs/DOCKER_SETUP.md), and
[authentication architecture](../docs/USERAUTH_ARCHITECTURE.md).
