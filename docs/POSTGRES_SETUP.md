# PostgreSQL Setup & Integration

> **Scope:** This page covers local Compose PostgreSQL only. Hosted Railway
> PostgreSQL provisioning and recovery are documented in
> [ENVIRONMENT_PROVISIONING.md](ENVIRONMENT_PROVISIONING.md) and
> [OPERATIONS.md](OPERATIONS.md).

## Version

PostgreSQL 16

------------------------------------------------------------------------

# Container Configuration

Configured in docker-compose.yml with:

-   POSTGRES_DB
-   POSTGRES_USER
-   POSTGRES_PASSWORD

Database is persisted via volume:

    postgres_data:/var/lib/postgresql/data

------------------------------------------------------------------------

# Migration Lifecycle

1.  makemigrations
2.  migrate
3.  django_migrations table tracks applied migrations

------------------------------------------------------------------------

# Inspecting Database

    docker compose exec db psql -U commerce -d commerce_db

View tables:

    \dt

Describe table:

    \d tablename

------------------------------------------------------------------------

# Why PostgreSQL?

-   ACID compliance
-   Strong relational integrity
-   Widely deployed in production environments
-   Docker compatible
