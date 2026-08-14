# Commerce Architect Frontend

React, TypeScript, and Vite implement the browser application. The current UI
renders the product list through the same-origin `/api/products/` endpoint.

## Local development

The preferred full-stack workflow is from the repository root:

```bash
podman-compose up --build -d
# or: docker compose up --build -d
```

The `frontend` service runs Vite and proxies `/api` to Django. For native
frontend work:

```bash
npm ci
npm run dev
```

See [`../docs/UI_SETUP.md`](../docs/UI_SETUP.md) for proxy and troubleshooting
details.

## Checks

```bash
npm test -- --run
npm run lint
npm run build
```

## Hosted runtime

`frontend/Dockerfile` runs tests, lint, and the production build in Node 24,
then copies only `dist` into NGINX. NGINX serves the SPA and proxies `/api/`,
`/admin/`, and `/static/` to Django over Railway private networking. Browser API
requests therefore remain same-origin. Requests for dotfiles are rejected
instead of falling through to the SPA. See
[`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md).
