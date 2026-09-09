# Commerce Architect

Commerce Architect is an ecommerce platform codebase built with PostgreSQL,
Django REST Framework, and React/Vite.

> **Project maturity:** Commerce Architect is an early-stage project under
> active development. The implemented catalog and authentication foundations
> are tested, but the platform is not yet a production release and does not yet
> provide a complete commerce experience or stable compatibility guarantees.

The application source is divided into two explicit component directories:

-   `backend/` contains the Django / DRF / Python application.
-   `frontend/` contains the React / Vite / TypeScript application.

Repository-level orchestration, CI configuration, and documentation remain at
the repository root.

------------------------------------------------------------------------

## Current Status

-   Django + DRF backend operational
-   PostgreSQL 16 locally and persistent PostgreSQL in hosted environments
-   React/Vite frontend with product and end-to-end authentication UI
-   Podman-compatible local development through the shared Compose file
-   Production-image validation and immutable deployment in GitHub Actions
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

## What Requires Other Validation

-   Django admin UI rendering
-   Pixel layout and responsive fit require real-browser/device acceptance;
    component tests do not prove rendered dimensions
-   Static branding assets

Admin is treated as a management surface, not core business logic.

## Testing Rules

1.  Tests enforce correct behavior --- we do not weaken tests to match
    bugs.
2.  Model contracts must be explicit and type-safe.
3.  API responses must match schema expectations.
4.  CI must pass before code is merged.

Changes are not ready to merge until CI passes.

------------------------------------------------------------------------

# CI Pipeline (GitHub Actions)

GitHub Actions builds the production frontend and backend images directly. It
validates those exact images, scans them with Trivy, and runs backend integration
tests against disposable PostgreSQL.

The workflow:

1.  Install locked frontend dependencies with Node.js 24
2.  Run the Vitest frontend suite
3.  Start disposable PostgreSQL and run pytest and Django checks against the
    production backend image
4.  Scan both validated images for fixed HIGH/CRITICAL findings
5.  Preserve immutable image identity for approved deployment automation

This checks both frontend and backend behavior while retaining an
OCI-container-based, portable local architecture.

------------------------------------------------------------------------

# Branching & Development Workflow

We follow a simplified GitFlow-inspired model.

## Branch Types

-   `main`
    -   Publication and release branch
    -   Receives reviewed changes from `develop`
-   `develop`
    -   Integration branch
    -   All features merge here first
-   Focused topic branches such as `feature/<name>`, `fix/<name>`, or
    `docs/<name>`
    -   One focused change per branch
    -   Must open PR into `develop`

------------------------------------------------------------------------

## CI Trigger Policy

CI validates pull requests targeting `develop` and manual runs. A push to
`develop` validates, publishes, and deploys immutable images to development,
then records the tested image digests. A reviewed `develop` to `main` pull
request promotes those exact digests to production after merge; `main` does not
rebuild the application images.

We do **not** run CI on every push to feature branches.

------------------------------------------------------------------------

## Pull Request Rules

Even as a solo developer:

-   All changes happen on a focused topic branch.
-   All changes go through PR review (even if self-reviewed).
-   CI must pass before merge.

This discipline prevents regressions and keeps integration reviewable as the
project grows.

------------------------------------------------------------------------

# Current Architecture Stack

Backend: - Django 6.1 - Django REST Framework - PostgreSQL 16

Frontend: - React - TypeScript - Vite - Tailwind CSS

Local containers: - Docker Compose - Podman Compose-compatible

Testing: - pytest - pytest-django - Vitest - React Testing Library

CI: - GitHub Actions - exact-image tests/scans - digest-based deployment

Future: - Stripe integration - Orders domain - Scheduling domain

## Project Policies

Commerce Architect uses component-specific software licenses. See
[`LICENSE.md`](LICENSE.md) for the licensing map and
[`CONTRIBUTING.md`](CONTRIBUTING.md) for the current contribution policy.
Report vulnerabilities privately according to [`SECURITY.md`](SECURITY.md).

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

# Documentation Map

-   [Developer onboarding](docs/DEVELOPER_ONBOARDING.md) — first-time setup and
    daily workflow
-   [Validation and PR reporting standards](docs/VALIDATION_STANDARDS.md) —
    canonical validation-summary structure and reporting rules
-   [Testing strategy](docs/TESTING_STRATEGY.md) — maintained automated test
    layers, production-image checks, and human-validation boundaries
-   [Docker and Podman setup](docs/DOCKER_SETUP.md) — local services,
    configuration, and checks
-   [Current architecture](docs/ARCHITECTURE.md) — canonical runtime
    topology and system boundaries
-   [Architecture record](docs/ARCHITECTURE_v1.2.md) — frozen Phase 1 design
    context, superseded where current implementation differs
-   [Platform philosophy](docs/PLATFORM_PHILOSOPHY.md) — enduring project and
    adoption principles
-   [Product roadmap](docs/ROADMAP.md) — current implementation and next steps
-   [Authentication architecture](docs/USERAUTH_ARCHITECTURE.md) — current
    account, token, verification, and recovery design
-   [Frontend and UX direction](docs/UX_ARCHITECTURE.md) — frontend technology,
    responsibility, and experience guardrails
-   [Build and deployment guide](docs/BUILD_DEPLOY.md) — provider-neutral build,
    provisioning, deployment, validation, and operations contract
-   [License map](LICENSE.md), [contribution guide](CONTRIBUTING.md), and
    [security policy](SECURITY.md) — repository policies

Milestone-specific implementation assignments and UAT records remain under
`docs/ai-prompts/` and `docs/uat-testing/`. They preserve implementation and
acceptance history; the current-state documents above take precedence.

------------------------------------------------------------------------

# Project Direction

Commerce Architect is intended to become:

-   A commercial-grade ecommerce platform
-   A reusable and understandable commerce architecture
-   A framework that adopters can deploy and operate for their own businesses or
    clients
-   A platform with intentional developer and operator experiences
-   An owner-controlled foundation for customization and extension
-   A scalable multi-domain system

These are project goals rather than claims about the current early-stage
implementation.
