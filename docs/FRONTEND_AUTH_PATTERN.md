# Frontend Authentication Pattern

The React frontend implements the Phase 1 hybrid JWT flow through its existing
fetch-based API client.

- Login uses `POST /api/auth/token/` with credentials included.
- The access token is held only in React memory and is sent as a Bearer token.
- The rotating refresh token stays in the backend's HttpOnly cookie and is never
  exposed to JavaScript.
- One startup call to `POST /api/auth/refresh/` can restore an existing session;
  a successful response is followed by `GET /api/auth/me/`.
- Failed startup refresh clears anonymous state. This slice does not implement a
  general concurrent-refresh/retry queue.
- No authentication token is written to localStorage or sessionStorage.
- Logout calls the backend and clears frontend state even when backend cleanup
  fails.

The UI provides registration, login, verification result, authenticated `/me`,
email change/reverification, and logout states. Verification links land on the
frontend, which removes token query parameters from history and explicitly POSTs
them to the backend so mail-link scanners do not consume tokens through GET.

Refresh cookies remain `HttpOnly`, `SameSite=Strict`, scoped to `/api/auth/`, and
`Secure` outside local development. The browser and API remain same-origin in
the current Vite and Railway/NGINX topologies. Any cross-site authentication
change requires a separate CORS, CSRF, and cookie-policy review.
