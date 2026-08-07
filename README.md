# Commerce Architect

Contains a design-time agent system for generating secure, minimalist ecommerce
architectures. Includes a clean codebase built on the best-in-class trifecta of technologies for data, backend/middleware and UX for modern Web applications.

------------------------------------------------------------------------

## Current Status

-   Architecture Agent v1: Stable
-   Gemini integration: Working
-   Normalization + schema enforcement: Enabled
-   Django + DRF backend operational
-   PostgreSQL running in Docker
-   CI (GitHub Actions) passing
-   Pytest test suite active

------------------------------------------------------------------------

# Project Philosophy

Commerce Architect is built with the following principles:

1.  **Minimalism**
    -   Avoid premature abstraction.
    -   Build only what is required for Phase 1 validation.
2.  **Security First**
    -   Reduce attack surface.
    -   Use proven, widely adopted technologies.
3.  **Reversibility**
    -   Every decision must be changeable without rewrite.
4.  **Owner-Controlled**
    -   Docker-based.
    -   PostgreSQL-backed.
    -   Cloud-agnostic.
5.  **Commercial Grade**
    -   Automated testing.
    -   CI enforcement.
    -   Clean branching discipline.
    -   Deterministic environments.

------------------------------------------------------------------------

# Testing Strategy

This project uses **pytest + pytest-django** as the primary test
framework.

We standardized on pytest early to avoid migrating test frameworks
later.

## What We Test

-   Health endpoint (`/health/`)
-   Domain models (e.g., Product model)
-   API endpoints (`/api/products/`)
-   Database integration (real Postgres via Docker)
-   Type correctness (e.g., Decimal enforcement)

## What We Do NOT Test

-   Django admin UI rendering
-   CSS or styling
-   Static branding assets

Admin is treated as a management surface, not core business logic.

## Testing Rules

1.  Tests enforce correct behavior --- we do not weaken tests to match
    bugs.
2.  Model contracts must be explicit and type-safe.
3.  API responses must match schema expectations.
4.  CI must pass before code is merged.

If CI fails, the branch is not production-ready.

------------------------------------------------------------------------

# CI Pipeline (GitHub Actions)

CI runs inside Docker using the same `docker-compose.yml` used locally.

The workflow:

1.  Build containers
2.  Start services
3.  Run pytest inside the web container
4.  Tear down services

This ensures parity between: - Local development - CI - Production-style
container runtime

------------------------------------------------------------------------

# Branching & Development Workflow

We follow a simplified GitFlow-inspired model.

## Branch Types

-   `main`
    -   Production-ready
    -   Stable
    -   Tagged releases only
-   `develop`
    -   Integration branch
    -   All features merge here first
-   `feature/<name>`
    -   One feature per branch
    -   Must open PR into `develop`

------------------------------------------------------------------------

## CI Trigger Policy

CI runs when: - A Pull Request targets `develop` - `develop` is merged
into `main` - Manually triggered via GitHub Actions

We do **not** run CI on every push to feature branches.

------------------------------------------------------------------------

## Pull Request Rules

Even as a solo developer:

-   All feature work happens on a feature branch.
-   All changes go through PR review (even if self-reviewed).
-   CI must pass before merge.

This discipline: - Prevents regression. - Makes scaling to multiple
contributors trivial. - Keeps production stable.

------------------------------------------------------------------------

# Current Architecture Stack

Backend: - Django 6.x - Django REST Framework - PostgreSQL 16 - Docker

Testing: - pytest - pytest-django

CI: - GitHub Actions - Docker-based pipeline

Future: - Stripe integration - Orders domain - Scheduling domain

------------------------------------------------------------------------

# Documentation

Detailed documentation is located in `/docs`:

-   [ARCHITECTURE_v1.2.md](docs/ARCHITECTURE_v1.2.md)
-   [DOCKER_SETUP.md](docs/DOCKER_SETUP.md)
-   [POSTGRES_SETUP.md](docs/POSTGRES_SETUP.md)
-   [DJANGO_ARCHITECTURE.md](docs/DJANGO_ARCHITECTURE.md)
-   [DRF_API.md](docs/DRF_API.md)
-   [CATALOG_DOMAIN.md](docs/CATALOG_DOMAIN.md)
-   [DEVOPS.md](docs/DEVOPS.md)
-   [STYLE_SETUP.md](docs/STYLE_SETUP.md)
-   [DEVELOPER_ONBOARDING.md](docs/DEVELOPER_ONBOARDING.md)
-   [TESTING_STRATEGY.md](docs/TESTING_STRATEGY.md)
-   [USERAUTH_ARCHITECTURE.md](docs/USERAUTH_ARCHITECTURE.md)
-   [UX_ARCHITECTURE.md](docs/UX_ARCHITECTURE.md)
-   [PRODUCTLIST_UX_v1_0.md](docs/PRODUCTLIST_UX_v1_0.md)
-   [LOGIN_ARCHITECTURE.md](docs/LOGIN_ARCHITECTURE.md)

# Usage

``` bash
npm run architecture inputs/example_retail.json
```

------------------------------------------------------------------------

# Production Intent

This repository is not a toy.

It is designed to become:

-   A commercial-grade ecommerce platform
-   A reusable architecture template
-   A client-deployable framework
-   A scalable multi-domain system

Every decision going forward should preserve that intent.
