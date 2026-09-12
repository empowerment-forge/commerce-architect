# Commerce Architect Backend

The backend is the Django and Django REST Framework API for Commerce Architect.
It uses PostgreSQL for application state and keeps authentication separate from
commerce domains.

The main apps are `accounts` for authentication, `catalog` for product-domain
behavior, and `health` for database-aware readiness. `media_storage` provides
provider-neutral immutable media storage adapters and delivery URL generation;
catalog models store only validated `sha256/<digest>` keys. Project
configuration lives in `config`.

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

## Catalog Portability v1 operator workflow

Catalog Portability is a trusted-operator capability scoped to one active
Organization. Enable it explicitly, then use the reviewed commands below from
the backend container:

```bash
podman-compose exec -T web python manage.py catalog_export \
  --organization <ORG_ID> --output /secure/path/catalog.zip
podman-compose exec -T web python manage.py catalog_validate \
  --organization <ORG_ID> --input /secure/path/catalog.zip --mode merge
podman-compose exec -T web python manage.py catalog_operation_status \
  --organization <ORG_ID> --operation-id <UUIDV4>
```

`catalog_import` requires the exact validated package/catalog digests and
explicit confirmation for `replace-storefront`; the default inventory policy
preserves live destination stock. `catalog_reset_storefront` is a
non-destructive, receipt-backed deactivation. `catalog_dev_purge` is reserved
for disposable development data, requires preview plus exact confirmation,
fails closed on references, and is denied in production. Never copy secrets
into commands, packages, logs, frontend code, or documentation. Use the
durable operation receipt to recover a lost acknowledgement before retrying.

The Product API exposes ordered ProductImage metadata and adapter-generated
public URLs. It selects an explicit primary image first, then the first
domain-sorted fallback; zero-image Products remain valid.

Django migrations live within each app's `migrations/` directory. Migration
files are reviewed schema changes; they do not seed application data or create
privileged users.

Local Compose configures persistent filesystem media and exposes only the
development GET/HEAD route through Vite. Hosted backends configure the
S3-compatible adapter entirely through `MEDIA_*` runtime settings. Storage
credentials remain backend-only and must never be committed, logged, rendered
to frontend code, or copied into documentation.

The API uses serializers as its transport boundary and keeps views thin;
business rules belong in models or domain services. PostgreSQL schema changes
are expressed through reviewed migrations.

For deeper detail, see the [current architecture](../docs/ARCHITECTURE.md),
[container setup](../docs/DOCKER_SETUP.md), and
[authentication architecture](../docs/USERAUTH_ARCHITECTURE.md).
