# Commerce Architect Frontend

The React, TypeScript, and Vite frontend exposes the product catalog and the
minimal registration, verification, login, account, email-change, and logout
journey.

Run the full stack from the repository root with `podman-compose up --build -d`
or `docker compose up --build -d`. For native frontend work:

```bash
npm ci
npm run dev
npm run test -- --run
npm run lint
npm run build
```

The browser calls same-origin `/api` routes. Access tokens remain in React memory
and refresh cookies remain HttpOnly. Local verification links are printed in the
backend logs. See [UI setup](../docs/UI_SETUP.md) and the
[frontend authentication pattern](../docs/FRONTEND_AUTH_PATTERN.md).
