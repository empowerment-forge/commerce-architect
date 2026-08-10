# Developer Onboarding Guide

## Purpose

This guide is the entry point for a Commerce Architect development environment.
The detailed backend and frontend instructions live in their dedicated setup
documents.

## Fresh-Clone Setup

1.  Clone the repository and enter its root directory:

    ```bash
    git clone https://github.com/anthonylpeterson/commerce-architect.git
    cd commerce-architect
    ```

2.  Install and verify one supported local container workflow:
    -   Podman with Podman Compose on Linux, including Pop!_OS
    -   Docker Desktop with Docker Compose, including Windows development through
        WSL2

    Verify the selected runtime with either:

    ```bash
    podman --version
    podman-compose --version
    ```

    or:

    ```bash
    docker version
    docker compose version
    ```

3.  No additional frontend configuration is required for the preferred Compose
    workflow. Compose supplies the development API proxy target and database
    connection settings. Host-side `npm install` or `npm ci` is **not required**;
    the frontend container installs the locked dependencies.

4.  Build and start the complete stack from the repository root:

    ```bash
    podman-compose up --build -d
    ```

    or:

    ```bash
    docker compose up --build -d
    ```

    This starts PostgreSQL (`db`), Django/DRF (`web`), and React/Vite
    (`frontend`).

5.  Apply the checked-in Django migrations:

    ```bash
    podman-compose exec web python manage.py migrate
    ```

    or:

    ```bash
    docker compose exec web python manage.py migrate
    ```

6.  Verify the services and open the application using the URLs below. Then see
    [DOCKER_SETUP.md](DOCKER_SETUP.md) for daily Compose operations and
    [UI_SETUP.md](UI_SETUP.md) for frontend behavior and optional native Vite
    development.

The repository's Compose file supports both documented local runtimes. GitHub
Actions CI uses Docker Compose.

This guide documents the current multi-step setup. A future
`DEV_WORKFLOW.md` and smaller standardized command surface are intended to
reduce onboarding friction, but those capabilities are not implemented or
documented as current commands yet.

## Access Points

-   React/Vite application: `http://localhost:5173/`
-   Django: `http://localhost:8000/`
-   Django admin: `http://localhost:8000/admin/`
-   Health check: `http://localhost:8000/health/`
-   Products API: `http://localhost:8000/api/products/`
-   Products API through the Vite proxy:
    `http://localhost:5173/api/products/`

## Normal Development Sequence

1.  Start the `db`, `web`, and `frontend` services with `podman-compose up -d`
    or `docker compose up -d` from the repository root.
2.  Verify all three services are running and confirm Django responds on port
    8000 and Vite responds on port 5173.
3.  Edit the bind-mounted frontend source normally; the Vite container provides
    hot module replacement without rebuilding the image.
4.  Run the relevant test suites: pytest in the backend container and Vitest from
    the frontend container. The exact commands are in the developer command
    quick reference in [DOCKER_SETUP.md](DOCKER_SETUP.md).
5.  Make focused changes on the appropriate feature branch, follow the repository
    pull-request workflow, and keep CI green.

## Architectural Philosophy

-   PostgreSQL persistence through a named container volume
-   Modular Django applications
-   A thin API layer with business rules owned by the backend
-   Owner-controlled infrastructure
-   A containerized, portable, and reversible development environment

The setup is designed to remain reproducible without making a single local
container runtime mandatory.
