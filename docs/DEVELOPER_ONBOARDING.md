# Developer Onboarding Guide

## Purpose

This guide is the entry point for a Commerce Architect development environment.
The detailed backend and frontend instructions live in their dedicated setup
documents.

## Initial Setup

1.  Clone the repository and enter its root directory.
2.  Choose a supported local container workflow:
    -   Podman with Podman Compose on Linux, including Pop!_OS
    -   Docker Desktop with Docker Compose, including Windows development through
        WSL2
3.  Follow [DOCKER_SETUP.md](DOCKER_SETUP.md) to build and start PostgreSQL,
    Django, and the React/Vite development server, apply migrations, and
    optionally create an admin user.
4.  Follow [UI_SETUP.md](UI_SETUP.md) for frontend container behavior, testing,
    hot reload, and the optional native Vite workflow.

The repository's Compose file supports both documented local runtimes. GitHub
Actions CI uses Docker Compose.

This guide documents the current multi-step setup. A future
`DEV_WORKFLOW.md` and smaller standardized command surface are intended to
reduce onboarding friction, but those capabilities are not implemented or
documented as current commands yet.

## Access Points

-   Django: `http://localhost:8000/`
-   Django admin: `http://localhost:8000/admin/`
-   Products API: `http://localhost:8000/api/products/`
-   React/Vite frontend: `http://localhost:5173/`

## Normal Development Sequence

1.  Start the `db`, `web`, and `frontend` containers with the commands in
    [DOCKER_SETUP.md](DOCKER_SETUP.md).
2.  Verify all three services are running and confirm Django responds on port
    8000 and Vite responds on port 5173.
3.  Edit the bind-mounted frontend source normally; the Vite container provides
    hot module replacement without rebuilding the image.
4.  Run the relevant test suites: pytest in the backend container and Vitest from
    the frontend project.
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
