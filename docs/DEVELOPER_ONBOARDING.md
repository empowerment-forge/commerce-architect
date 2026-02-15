# Developer Onboarding Guide

## Setup Steps

1.  Install Docker Desktop

2.  Enable WSL 2 integration (or use Linux/Mac)

3.  Clone repository

4.  Run:

    docker compose up --build

5.  Apply migrations:

    docker compose exec web python manage.py migrate

6.  Create superuser:

    docker compose exec web python manage.py createsuperuser

------------------------------------------------------------------------

# Access Points

Django: http://localhost:8000 Admin: http://localhost:8000/admin API:
http://localhost:8000/api/products/

------------------------------------------------------------------------

# Development Cycle

-   Modify models
-   Run makemigrations
-   Run migrate
-   Test API
-   Commit changes

------------------------------------------------------------------------

# Architectural Philosophy

-   Docker-first
-   PostgreSQL persistence
-   Modular Django apps
-   Thin API layer
-   Owner-controlled infrastructure
