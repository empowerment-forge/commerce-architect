# Docker Setup & Configuration

## Purpose

This document explains every step taken to containerize Django and
PostgreSQL for local development in WSL2 using Docker Desktop.

This process MUST be followed exactly for repeatability.

------------------------------------------------------------------------

# Prerequisites

1.  Install Docker Desktop (Windows).

2.  Enable WSL2 integration inside Docker Desktop settings.

3.  Verify Docker works inside WSL:

    docker version

4.  Test Docker runtime:

    docker run hello-world

If this works, Docker is properly integrated.

------------------------------------------------------------------------

# Architecture Overview

Docker services:

-   web → Django application container
-   db → PostgreSQL 16 container

Database persistence is handled via a Docker volume.

------------------------------------------------------------------------

# First Build

Build and run:

    docker compose up --build

This will:

-   Build the Django image
-   Pull PostgreSQL image
-   Create Docker network
-   Start both containers
-   Stream logs

Access:

    http://localhost:8000/

------------------------------------------------------------------------

# Stop Containers

    docker compose down

Stops containers but preserves database volume.

------------------------------------------------------------------------

# Restart Web Container

    docker compose restart web

Use after configuration or dependency changes.

------------------------------------------------------------------------

# Migration Workflow (Critical)

Step 1 -- Generate Migration Files:

    docker compose exec web python manage.py makemigrations

This scans models.py and creates migration instructions.

Step 2 -- Apply Migrations:

    docker compose exec web python manage.py migrate

This applies schema changes to PostgreSQL.

------------------------------------------------------------------------

# Create Admin User

    docker compose exec web python manage.py createsuperuser

This creates a record in auth_user table.

Access admin panel:

    http://localhost:8000/admin/

------------------------------------------------------------------------

# Access PostgreSQL

    docker compose exec db psql -U commerce -d commerce_db

Useful commands:

    \dt
    \d tablename
    \q

------------------------------------------------------------------------

# Full Reset (Destructive)

WARNING: Deletes all data.

    docker compose down -v
    docker compose up --build

------------------------------------------------------------------------

# Development Notes

-   Django runs on 0.0.0.0:8000
-   Database host inside Docker is "db"
-   Containers communicate via internal Docker network
-   Rebuild only when Dockerfile or requirements.txt changes
