# Frontend Setup & Development

## Purpose

This document is the practical setup and daily-use reference for the Commerce
Architect frontend. It explains how to install its dependencies, run its tests,
start and view the development server, and stop it when finished.

## Frontend stack

The frontend uses:

- React for the user interface
- TypeScript for typed application code
- Vite for the development server and production build
- Vitest for frontend tests
- React Testing Library for rendering and testing React behavior
- Tailwind CSS for utility-first styling

The frontend is an independent Node project under `frontend/`. Its npm scripts,
dependencies, and lockfile are separate from the Django backend.

## Prerequisites

- Node.js and npm. Install Node through your normal Node version manager or
  development environment. The current CI workflow uses Node.js 20.
- Running backend services for API-backed UI functionality. The Django API and
  PostgreSQL database run through this repository's Docker/Podman Compose setup.

Follow [DOCKER_SETUP.md](DOCKER_SETUP.md) to build, start, migrate, and stop the
backend services. This guide does not duplicate that setup.

## Install frontend dependencies

From the repository root:

```bash
cd frontend
npm ci
```

`cd frontend` enters the independent frontend project. `npm ci` performs a clean,
deterministic dependency installation from `package-lock.json`. It removes an
existing `node_modules` directory before installing and fails when the lockfile
does not agree with `package.json`. Because it installs the exact dependency tree
recorded in the checked-in lockfile, it is preferred over a general `npm install`
when reproducing the repository's known environment.

Run `npm ci` after cloning the repository and whenever the checked-in frontend
dependency files change.

## Run frontend tests

From `frontend/`, run the complete test suite once:

```bash
npm run test -- --run
```

The `test` script in `frontend/package.json` invokes Vitest. The npm `--`
separator ends npm's own argument processing and forwards the following option to
Vitest. Vitest's `--run` option runs the suite once and exits instead of remaining
active to watch for file changes. This is also the command used by the current CI
workflow.

For an interactive development session, the repository defines a dedicated watch
script:

```bash
npm run test:watch
```

That script invokes `vitest --watch`. Vitest runs the tests and stays active,
rerunning relevant tests as files change. Press `Ctrl+C` to leave watch mode.

## Start the development server

From `frontend/`:

```bash
npm run dev
```

The `dev` script invokes Vite. Vite starts the local development server, serves
the React application, and updates the browser as frontend files change. Keep this
terminal running while working with the UI.

## View the application

Open the following address in a browser:

```text
http://localhost:5173/
```

The currently implemented UI is the Commerce Architect product-list frontend. It
requests the product collection from the Django API and displays loading, error,
empty, or product-card states based on the response.

## Frontend/backend development architecture

During local development, requests follow this path:

```text
Browser
   -> Vite development server on localhost:5173
   -> /api proxy
   -> Django/DRF on localhost:8000
   -> PostgreSQL
```

The product page requests `/api/products/`. In `frontend/vite.config.ts`, Vite is
configured to proxy every request beginning with `/api` to
`http://localhost:8000`, with `changeOrigin: true`. The browser therefore sends a
same-origin request to the Vite server on port 5173, and Vite forwards it to the
Django/DRF backend on port 8000. The `/api` path is preserved. Django then reads
the product data from PostgreSQL.

This proxy applies while using the Vite development server. The API client also
supports a `VITE_API_BASE_URL` environment value, but when it is unset—as in the
normal local setup—it uses relative `/api` paths and the Vite proxy.

## Verify backend services before starting the UI

From the repository root, check the Compose services:

```bash
docker compose ps
```

This uses Docker Compose to list the current project containers and their state.
Expect the `web` service (Django) and `db` service (PostgreSQL) to be running. The
frontend needs Django available on port 8000 for proxied API requests, and Django
needs PostgreSQL available to retrieve product data. If either service is down,
the page may show its API error state instead of products.

If your environment uses the standalone Podman Compose command for this same
Compose file, the equivalent status check is:

```bash
podman-compose ps
```

Use the container tooling already established for your development environment.
See [DOCKER_SETUP.md](DOCKER_SETUP.md) for the repository's backend startup and
shutdown workflow.

## Stop the frontend

Press `Ctrl+C` in the terminal running `npm run dev`. This interrupts Vite and
stops the frontend development server. It does not stop the backend containers;
manage those separately using the commands in [DOCKER_SETUP.md](DOCKER_SETUP.md).

## Useful npm commands

Run these commands from `frontend/`. This list reflects the scripts currently
defined in `frontend/package.json`.

| Command | Purpose |
| --- | --- |
| `npm run dev` | Starts the Vite development server for local UI work. |
| `npm run test -- --run` | Invokes the `test` script and forwards `--run` to Vitest so the suite runs once and exits. |
| `npm run test:watch` | Runs Vitest in watch mode and reruns tests as relevant files change. |
| `npm run build` | Runs the TypeScript build check with `tsc -b`, then creates the production frontend bundle with Vite. |
| `npm run lint` | Runs ESLint across the frontend project to report configured lint violations. |
| `npm run preview` | Starts Vite's local preview server for the previously built production bundle; run `npm run build` first. |

## Development workflow

A normal frontend session is:

1. From the repository root, start the backend as described in
   [DOCKER_SETUP.md](DOCKER_SETUP.md), or confirm it is running with
   `docker compose ps` (or `podman-compose ps` in that environment).
2. Enter the frontend project with `cd frontend`.
3. Run `npm ci` after a fresh clone or when dependency files have changed.
4. Run `npm run test -- --run` to verify the frontend suite once.
5. Run `npm run dev` and leave that terminal active.
6. Browse to `http://localhost:5173/` and work with the product-list UI.
7. Press `Ctrl+C` in the Vite terminal to stop the frontend server.
