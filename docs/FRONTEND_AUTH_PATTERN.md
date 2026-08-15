# Frontend Authentication Pattern

The React frontend implements the Phase 1 hybrid JWT flow through its existing
fetch-based API client.

- Login uses `POST /api/auth/token/` with credentials included.
- The access token is held only in React memory and is sent as a Bearer token.
- The rotating refresh token stays in the backend's HttpOnly cookie and is never
  exposed to JavaScript.
- One startup call to `POST /api/auth/refresh/` can restore an existing session;
  a successful response is followed by `GET /api/auth/me/`.
- Authenticated requests use the current in-memory access token. On a 401 they
  share one in-progress refresh-cookie request, replace the access token in
  memory, and retry the original request exactly once. Refresh failure clears
  local authentication state and returns the UI to login.
- No authentication token is written to localStorage or sessionStorage.
- Logout calls the backend and clears frontend state even when backend cleanup
  fails.

The UI provides registration, login, password recovery, verification result,
authenticated `/me`, email change/reverification, and logout states. Login has
a secondary `Forgot password?` view whose successful request always shows the
same check-email message. Recovery links land on `/reset-password`; the page
captures the UUID/token in component memory, immediately removes the query from
browser history, and changes state only through POST. Password mismatch is
checked locally, while Django validator feedback remains authoritative. Reset
success clears in-memory authentication state and returns to login without
automatically issuing credentials.

Verification links follow the same scanner-safe pattern: the frontend removes
token query parameters from history and explicitly POSTs them to the backend so
mail-link scanners do not consume tokens through GET.

Refresh cookies remain `HttpOnly`, `SameSite=Strict`, scoped to `/api/auth/`, and
`Secure` outside local development. The browser and API remain same-origin in
the current Vite and Railway/NGINX topologies. Any cross-site authentication
change requires a separate CORS, CSRF, and cookie-policy review.
