# Frontend Setup & Development

## Purpose

This document is the practical setup and daily-use reference for the Commerce
Architect frontend. It explains the preferred Compose-managed workflow, frontend
checks, live development behavior, and the optional native Vite workflow.

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

## Preferred Development Mode: Compose

The preferred local workflow runs PostgreSQL, Django, and the Vite development
server together through Compose. From the repository root, follow
[DOCKER_SETUP.md](DOCKER_SETUP.md) and run either:

```bash
docker compose up --build -d
```

or:

```bash
podman-compose up --build -d
```

The frontend is then available at `http://localhost:5173/`. Its source directory
is bind-mounted into the container, so Vite detects host edits and provides hot
module replacement without an image rebuild.

The frontend implementation remains entirely under `frontend/`, while Vite runs
inside the Compose container named `commerce_frontend`.

The frontend image uses Node.js 24 and installs dependencies with `npm ci` from
`frontend/package-lock.json`. A separate `frontend_node_modules` volume mounted
at `/app/node_modules` prevents the source bind mount from replacing the
container's Linux dependencies. The startup command runs `npm ci` so this volume
stays synchronized with the lockfile. Host-side `npm install` or `npm ci` is not
required for the Compose workflow.

For frontend checks in the preferred mode, run the npm scripts inside the
container from the repository root:

```bash
docker compose exec -T frontend npm run test -- --run
docker compose exec -T frontend npm run build
docker compose exec -T frontend npm run lint
```

Use `podman-compose` in place of `docker compose` for the Podman workflow.

## Optional Development Mode: Native Vite

Running Vite directly on the host remains supported when useful. This optional
workflow requires Node.js 24 and npm on the host, plus the Compose `web` and `db`
services for API-backed UI functionality.

From the repository root:

```bash
cd frontend
npm ci
npm run dev
```

`cd frontend` enters the independent frontend project. `npm ci` performs a clean,
deterministic dependency installation from `package-lock.json`. It removes an
existing `node_modules` directory before installing and fails when the lockfile
does not agree with `package.json`. Because it installs the exact dependency tree
recorded in the checked-in lockfile, it is preferred over a general `npm install`
when reproducing the repository's known environment.

For this optional native mode, run `npm ci` after cloning the repository and
whenever the checked-in frontend dependency files change. `npm run dev` starts
Vite on `http://localhost:5173/`. When `VITE_API_PROXY_TARGET` is unset, native
Vite proxies `/api` to `http://localhost:8000`, where the Compose `web` service is
published to the host.

## Native Frontend Commands

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

## View the application

Open the following address in a browser:

```text
http://localhost:5173/
```

The currently implemented UI is the Commerce Architect product-list frontend. It
requests the product collection from the Django API and displays loading, error,
empty, or product-card states based on the response.

## Frontend/backend development architecture

During preferred Compose-managed local development, requests follow this path:

```text
Browser
   -> Vite development server on localhost:5173
   -> /api proxy
   -> Django/DRF at web:8000 on the Compose network
   -> PostgreSQL
```

The product page requests `/api/products/`. In `frontend/vite.config.ts`, Vite is
configured to proxy every request beginning with `/api` to
the `VITE_API_PROXY_TARGET` value. Compose sets that value to
`http://web:8000`, because `localhost` inside the frontend container would refer
to the frontend container itself. When Vite is run natively and the variable is
unset, the target defaults to `http://localhost:8000`. The browser sends a
same-origin request to Vite on port 5173, Vite preserves the `/api` path and
forwards it to Django, and Django reads product data from PostgreSQL.

This proxy applies while using the Vite development server. The API client also
supports a `VITE_API_BASE_URL` environment value, but when it is unset—as in the
normal local setup—it uses relative `/api` paths and the Vite proxy.

## Verify the development services

From the repository root, check the Compose services:

```bash
docker compose ps
```

This uses Docker Compose to list the current project containers and their state.
Expect the `frontend` (Vite), `web` (Django), and `db` (PostgreSQL) services to be
running. The frontend needs Django available as `web:8000` for proxied API
requests, and Django needs PostgreSQL available as `db:5432` to retrieve product
data. If either backend service is down, the page may show its API error state
instead of products.

If your environment uses the standalone Podman Compose command for this same
Compose file, the equivalent status check is:

```bash
podman-compose ps
```

Use the container tooling already established for your development environment.
See [DOCKER_SETUP.md](DOCKER_SETUP.md) for the complete development stack's
startup, shutdown, status, logs, and test commands.

## Stop the frontend

For the preferred Compose workflow, stop the complete development stack from the
repository root with `docker compose down` or `podman-compose down`. For native
Vite, press `Ctrl+C` in the terminal running `npm run dev`; this stops only the
host Vite process.

## Optional Native npm Commands

When using the optional native mode, run these commands from `frontend/`. This
list reflects the scripts currently defined in `frontend/package.json`.

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

1. From the repository root, start the complete stack as described in
   [DOCKER_SETUP.md](DOCKER_SETUP.md), or confirm it is running with
   `docker compose ps` (or `podman-compose ps` in that environment).
2. Browse to `http://localhost:5173/` and work with the product-list UI; Vite
   reloads the browser as bind-mounted frontend source changes.
3. Run frontend checks through the container when needed, for example
   `docker compose exec -T frontend npm run test -- --run` (or the equivalent
   Podman Compose command).
4. Stop the stack with the Compose `down` command for the selected runtime.

This local development container is not a production frontend deployment
decision. A future production environment may build the React application and
host the resulting assets through a dedicated frontend or static hosting
provider instead of running Vite. Local containerized PostgreSQL likewise does
not determine the production database deployment model; managed PostgreSQL
remains a valid future option.
