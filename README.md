# Commerce Architect

Commerce Architect is an ecommerce platform codebase built with PostgreSQL,
Django REST Framework, and React/Vite.

The application source is divided into two explicit component directories:

-   `backend/` contains the Django / DRF / Python application.
-   `frontend/` contains the React / Vite / TypeScript application.

Repository-level orchestration, CI configuration, and documentation remain at
the repository root.

------------------------------------------------------------------------

## Current Status

-   Django + DRF backend operational
-   PostgreSQL 16 running in a containerized local environment
-   React/Vite frontend with a product-list UI
-   Podman-compatible local development through the shared Compose file
-   Docker Compose-based CI in GitHub Actions
-   Pytest backend tests and Vitest frontend tests

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
    -   OCI-container-based and Docker/Podman-compatible.
    -   PostgreSQL-backed.
    -   Cloud-agnostic.
5.  **Commercial Grade**
    -   Automated testing.
    -   CI enforcement.
    -   Clean branching discipline.
    -   Deterministic environments.

Commerce Architect is intended to become an understandable, owner-controlled,
and adoptable commerce architecture that developers and organizations can
deploy, customize, and extend. The enduring principles and explicitly labeled
target experience are described in
[PLATFORM_PHILOSOPHY.md](docs/PLATFORM_PHILOSOPHY.md).

------------------------------------------------------------------------

# Testing Strategy

The backend uses **pytest + pytest-django**. The React frontend uses **Vitest +
React Testing Library**.

## What We Test

-   Health endpoint (`/health/`)
-   Domain models (e.g., Product model)
-   API endpoints (`/api/products/`)
-   Database integration (real PostgreSQL through the containerized environment)
-   React component and API-client behavior
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

GitHub Actions CI uses Docker Compose with the same `docker-compose.yml` that is
compatible with local Docker Compose and Podman Compose workflows.

The workflow:

1.  Install locked frontend dependencies with Node.js 24
2.  Run the Vitest frontend suite
3.  Build and start the `db` and `web` Docker Compose services for backend
    integration testing
4.  Run pytest inside the `web` container
5.  Tear down the services

This checks both frontend and backend behavior while retaining an
OCI-container-based, portable local architecture.

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

Backend: - Django 6.x - Django REST Framework - PostgreSQL 16

Frontend: - React - TypeScript - Vite - Tailwind CSS

Local containers: - Docker Compose - Podman Compose-compatible

Testing: - pytest - pytest-django - Vitest - React Testing Library

CI: - GitHub Actions - Docker Compose-based pipeline

Future: - Stripe integration - Orders domain - Scheduling domain

## Licensing and Contributions

Commerce Architect uses component-specific software licenses. See
[`LICENSE.md`](LICENSE.md) for the licensing map and
[`CONTRIBUTING.md`](CONTRIBUTING.md) for the current contribution policy.

## Local Development

The preferred local development workflow uses the shared Compose configuration
to run the complete stack:

-   PostgreSQL (`db`)
-   Django / DRF (`web`)
-   React / Vite (`frontend`)

The checked-in Compose file is explicitly a development configuration. It
supplies labeled local-only Django and PostgreSQL values so
`podman-compose up --build -d` and `docker compose up --build -d` remain
convenient. Production uses `COMMERCE_ENV=production` and fails startup when its
required secret, host, or database configuration is absent or unsafe. See
[DOCKER_SETUP.md](docs/DOCKER_SETUP.md) for the environment-variable and Django
deployment-check reference. [`.env.example`](.env.example) contains safe local
examples only.

Start with [DEVELOPER_ONBOARDING.md](docs/DEVELOPER_ONBOARDING.md) after cloning
the repository. [DOCKER_SETUP.md](docs/DOCKER_SETUP.md) is the detailed Compose
operations reference, and [UI_SETUP.md](docs/UI_SETUP.md) covers frontend-specific
development and the optional native Vite workflow.

------------------------------------------------------------------------

# Documentation

Detailed documentation is located in `/docs`:

-   [ARCHITECTURE_v1.2.md](docs/ARCHITECTURE_v1.2.md)
-   [PLATFORM_PHILOSOPHY.md](docs/PLATFORM_PHILOSOPHY.md)
-   [ROADMAP.md](docs/ROADMAP.md)
-   [DOCKER_SETUP.md](docs/DOCKER_SETUP.md)
-   [UI_SETUP.md](docs/UI_SETUP.md)
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

## Project Roadmap

[docs/ROADMAP.md](docs/ROADMAP.md) is the living view of the platform's current
implementation state and major next steps. Architecture documentation describes
the intended system design and constraints, while GitHub issues contain detailed
implementation work and acceptance criteria. The roadmap connects those levels
and evolves as major implementation slices are completed or priorities
materially change.

# Architecture Tool History

The original architecture-generation tool was extracted into the separate
[commerce-architecture-agent](https://github.com/anthonylpeterson/commerce-architecture-agent)
repository. Commerce Architect does not depend on that tool.

------------------------------------------------------------------------

# Production Intent

This repository is not a toy.

It is designed to become:

-   A commercial-grade ecommerce platform
-   A reusable and understandable commerce architecture
-   A framework that adopters can deploy and operate for their own businesses or
    clients
-   A platform with intentional developer and operator experiences
-   An owner-controlled foundation for customization and extension
-   A scalable multi-domain system

These are production goals, not a claim that the repository is production-ready
today. Every decision going forward should preserve that intent.
