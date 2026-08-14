# Implementation Assignment: Registration and Email Verification

> **Status: implemented on `feature/auth-registration-verification`.** This
> approved assignment remains the acceptance contract for review and future
> regression work.

## Objective

Implement a small, independently testable end-to-end authentication slice that a
developer can exercise locally without knowing the test suite. Preserve the
existing hybrid JWT architecture and keep identity concerns inside `accounts`,
separate from catalog and future commerce domains.

The required journey is:

```text
register
→ receive verification email
→ open frontend verification link
→ verify account
→ log in
→ see authenticated /me state
→ log out
```

## 1. Current authentication baseline

The backend uses Django's stock `django.contrib.auth.models.User`; no
`AUTH_USER_MODEL` override exists. `accounts` currently provides:

- `POST /api/auth/register/`: creates an active user from username, email, and
  a password with serializer `min_length=8`; returns ID, username, and email.
- `POST /api/auth/token/`: SimpleJWT credential login; returns a 10-minute access
  token as `{ "access": "..." }` and sets a 7-day `refresh_token` cookie.
- `POST /api/auth/refresh/`: reads the HttpOnly cookie, rotates/blacklists it,
  and returns a new access token.
- `POST /api/auth/logout/`: blacklists a usable refresh token when present and
  always clears the cookie.
- `GET /api/auth/me/`: requires a Bearer access token and returns ID, username,
  and email.

The refresh cookie is HttpOnly, `SameSite=Strict`, scoped to `/api/auth/`, and
`Secure` outside local development. Access tokens are not cookies and must stay
in frontend memory. The same-origin Vite/NGINX topology avoids a permissive CORS
requirement.

Backend coverage exists in `backend/tests/test_auth_api.py`. The frontend has a
small fetch-based `apiGet` helper that can attach a Bearer token, but no auth
store, forms, router, refresh lifecycle, or authenticated UI.

Known baseline limitations relevant to this assignment:

- registration does not call Django's configured password validators;
- email is neither required nor uniquely enforced by the stock `User` model;
- there is no verification state, email backend configuration, or email flow;
- all newly registered users can currently obtain tokens immediately.

## 2. Scope and user-visible goals

Deliver one minimal usable slice:

- A visitor can register with username, email, and password.
- Registration creates a verification requirement and sends one verification
  email through the configured Django email backend.
- The email links to a frontend result page, not directly to a state-changing
  GET endpoint.
- The frontend submits the token for verification and clearly reports success,
  invalid, expired, and already-used states.
- A verified user can log in through the existing token endpoint.
- The UI loads `/api/auth/me/` with the in-memory access token and shows the
  authenticated username/email and verification status.
- An authenticated user can change their email address and is clearly told that
  the new normalized address must be verified independently.
- Logout clears backend refresh state and all frontend access/auth state.
- Common validation and authentication failures are understandable without
  opening developer tools.

Keep styling intentionally modest and consistent with the existing frontend.

## 3. Backend behavior

Keep the current routes and JWT/cookie semantics compatible. Extend registration
to:

1. Require a nonblank normalized email address.
2. Reject a username or normalized email already reserved by another account.
3. Validate the password with Django's configured password validators, passing
   a prospective user so similarity validation works.
4. Create the user and verification state atomically.
5. Generate a verification token, store only its digest, and send the frontend
   verification URL after the database transaction commits.
6. Return safe account/status metadata but no access or refresh token.

Email sending failure must not leave an ambiguous half-created account. Use an
explicit, tested policy: retain the unverified account and return a clear
retryable delivery error, with the resend endpoint as recovery. Do not log the
raw token or email body.

Add verification status to `/api/auth/me/` without removing its existing
fields. Login enforcement must be controlled by a setting rather than embedded
as an irreversible policy. When enforcement is enabled, correct credentials for
an unverified account return the specified `email_not_verified` response and no
tokens/cookie. Existing logout and refresh behavior remains unchanged.

## 4. Email verification lifecycle

- Registration reserves the normalized address and issues one active token.
- A verification message contains a configurable absolute frontend URL such as
  `http://localhost:5173/verify-email?uid=<public-id>&token=<secret>`.
- Loading that frontend URL performs no server-side mutation by GET alone. The
  page explicitly submits `POST /api/auth/verify-email/`, avoiding accidental
  consumption by mail-link scanners.
- Successful verification atomically sets `verified_at`, invalidates the token,
  and returns the current verification state.
- Reuse of a successfully consumed token is idempotent from the user's
  perspective: return a stable `already_verified` result without changing data.
- Invalid, tampered, superseded, or expired tokens return a generic safe error.
- `POST /api/auth/resend-verification/` rotates any prior token and sends a new
  message for an eligible unverified account.
- Resend uses an enumeration-resistant response and is rate-limit-ready. A
  minimal in-model cooldown is acceptable; adding a third-party throttling
  dependency is not.

### Email-address change and reverification

Verification applies only to the exact normalized email stored when the token
was issued. It is never a permanent user-level flag that survives an address
change.

An authenticated email change must use one accounts-owned service operation and
one database transaction to:

1. Normalize and validate the requested address and reserve it under the same
   case-insensitive uniqueness rule as registration.
2. Update `User.email` and the verification record's `normalized_email`.
3. Clear `verified_at` immediately, before reporting success.
4. Invalidate the previous token digest and issue a new token bound to the new
   normalized address.
5. Send a verification message only to the new address after commit.

A token is valid only when its bound normalized address still matches both the
verification record and current `User.email`. Consequently, every stale token
for the previous address must fail even if it has not reached its original
expiry. Resend looks up and sends only to the account's current normalized
address; it must never revive, target, or reveal a prior address.

When login enforcement is enabled, changing the address makes subsequent
credential login return `email_not_verified` until the new address succeeds.
When enforcement is disabled, login may continue but `/me` must still report the
new address as unverified. This slice does not automatically revoke already
issued access or refresh tokens on email change; an existing authenticated
session may continue and must observe the new unverified state through `/me`.
That session policy must be documented and tested rather than inferred.

Audit and security events, if recorded, must distinguish the actor/user ID, old
normalized address, new normalized address, verification invalidation time, and
later verification time without recording raw tokens. A verified timestamp must
never be presented without the normalized address it applies to.

## 5. Verification-token and security requirements

- Generate at least 256 bits of randomness with Python's `secrets` module.
- Store only a SHA-256 or stronger digest, never the raw token.
- Bind the token to exactly one verification record/user and normalized email.
- Tokens are single-use, expire after a configurable lifetime, and are replaced
  on resend. Verification and resend updates must be transaction-safe.
- Use constant-time digest comparison.
- Do not put secrets in logs, analytics, error responses, fixtures, or committed
  configuration. Query parameters are acceptable only on the frontend landing
  URL; clear them from browser history/state after capture when practical.
- Do not issue JWTs or refresh cookies from registration or verification.
- Preserve the existing HttpOnly/Secure/SameSite/path refresh-cookie controls.
- Keep access tokens in memory only; never use localStorage or sessionStorage.
- Apply Django password validation and return field-oriented errors without
  leaking sensitive account details.
- Treat normalized emails case-insensitively and prevent concurrent duplicate
  reservations at the database layer.
- Verification responses must not disclose whether unrelated addresses or users
  exist. Resend should return 202 with the same public message for unknown,
  already verified, cooldown-limited, and accepted addresses.

## 6. Frontend user flows

Implement the smallest routing/state structure needed for:

- Register page/form: username, email, password, submit state, field errors, and
  a success message directing the user to check email.
- Login page/form: username and password, clear invalid-credential and
  email-not-verified messages, and navigation to authenticated state.
- Verification result page: reads `uid` and `token`, submits verification once,
  removes/obscures token query data when practical, and renders pending,
  success, already verified, expired/invalid, and network-failure states.
- Authenticated view: uses the in-memory access token with
  `GET /api/auth/me/` and displays username, email, and `email_verified`.
- Authenticated email change: submits the new address, updates the displayed
  `/me` state to the current unverified address, and directs the user to the new
  verification email.
- Logout action: calls the backend with credentials included, then clears local
  state even if the server says the cookie is absent/invalid.

All cookie-dependent fetches (`token`, `refresh`, `logout`) must use
`credentials: "include"`. Keep the access token out of persistent browser
storage. On a page reload, the UI may make one refresh request to restore a
session, then load `/me`; coordinate this as one request, without implementing a
general concurrent-refresh queue in this slice. Clear state on failed refresh.

Use the existing API client style and avoid introducing Axios, a large state
library, or a component framework solely for this feature.

## 7. Configuration and environment requirements

Add documented settings with safe local defaults and explicit hosted values:

| Setting/environment variable | Purpose |
|---|---|
| `AUTH_REQUIRE_VERIFIED_EMAIL` | Enables login enforcement; default `false` for backward compatibility, set `true` in the local manual-test profile and intended new hosted environments after existing-account review |
| `AUTH_EMAIL_VERIFICATION_TTL_SECONDS` | Token lifetime; suggested default 86400 |
| `AUTH_EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS` | Minimum resend interval; suggested default 60 |
| `AUTH_FRONTEND_BASE_URL` | Trusted absolute frontend origin used to build links; local example `http://localhost:5173` |
| `EMAIL_BACKEND` | Django email backend; console backend for local development |
| provider-specific email settings | Hosted sender/SMTP/API values, supplied only through environment secrets |
| `DEFAULT_FROM_EMAIL` | Non-secret sender identity |

Fail closed in production when enforcement/email delivery is enabled but the
frontend URL, sender, or delivery backend is unsafe or missing. Never accept an
arbitrary request-provided redirect URL. Update `.env.example` and applicable
setup docs during implementation, but do not commit real provider credentials.

For local manual testing, the console email backend must print the message/link
to backend logs so no external email account is required.

## 8. API endpoints and response behavior

Preserve trailing slashes and the current `/api/auth/` namespace.

### `POST /api/auth/register/`

Request:

```json
{"username":"alice","email":"alice@example.com","password":"correct horse battery staple"}
```

Success: 201 with `id`, `username`, normalized `email`,
`email_verified: false`, and a safe `detail`. No tokens. Validation failures:
400 with field-keyed DRF errors. A retryable email-delivery failure must have a
stable machine-readable code and must not expose provider details.

### `POST /api/auth/verify-email/`

Request: `{ "uid": "<opaque-record-id>", "token": "<raw-token>" }`.
Success: 200 with `email_verified: true`, `verified_at`, and code `verified`.
The response also includes the normalized `email` that was verified. Already
verified: 200 with code `already_verified` and that same address.
Invalid/expired/superseded: 400 with generic code
`invalid_or_expired_token`.

### `POST /api/auth/resend-verification/`

Request: `{ "email": "alice@example.com" }`. Public response: always 202 with
the same detail text for syntactically valid email input. Malformed input may
return 400. Do not reveal account state. For an eligible account, delivery must
target only the current normalized `User.email`; a former address cannot be used
to select the account or receive a new token.

### `POST /api/auth/change-email/`

Requires a Bearer access token. Request: `{ "email": "new@example.com" }`.
Success: 200 with the current normalized `email`, `email_verified: false`, and a
safe check-your-email detail. The operation atomically changes the address,
invalidates prior verification and tokens, and issues a token for the new
address. Invalid/duplicate input returns field-keyed 400 errors. Delivery
failure follows the same retained-unverified-account and resend recovery policy
as registration, without restoring the old address or verified state.

### `POST /api/auth/token/`

Keep the existing request and successful response/cookie contract. When
`AUTH_REQUIRE_VERIFIED_EMAIL=true`, an unverified account receives 403 with
`{ "code": "email_not_verified", "detail": "..." }` and no refresh cookie.
Invalid credentials remain 401 with a generic message.

### Existing refresh, logout, and `/me`

- `POST /api/auth/refresh/`: unchanged 200 access response/rotated cookie or 401.
- `POST /api/auth/logout/`: unchanged idempotent 200 and cookie clearing.
- `GET /api/auth/me/`: unchanged authentication requirement and existing fields;
  add `email_verified` and nullable `email_verified_at`. The boolean/timestamp
  apply to the `email` in that same response only.

## 9. Automated test requirements

Backend tests must cover:

- successful registration, normalized email, verification record, password
  hashing/validators, and no token issuance;
- duplicate username and case-insensitive duplicate email, including database
  uniqueness behavior;
- message recipient, sender, link origin/path, and absence of raw-token storage;
- transaction/delivery failure policy;
- valid verification, expiry, tampering, wrong record, resend supersession,
  single use, and idempotent already-verified behavior;
- verified-user email change atomically updates `User.email` and the verification
  record, clears `verified_at`, and invalidates the old token;
- an old verification link cannot verify the former or current address after an
  email change, while the newly issued link verifies the new address;
- email-change delivery targets only the new address, and resend accepts/sends
  only for the current address without reviving stale state;
- enumeration-resistant resend and cooldown;
- enforcement setting on/off after email change, with no cookie on rejected new
  login when enabled and permitted login remaining explicitly unverified when
  disabled;
- `/me` returns the current email and matching verification state before and
  after reverification;
- regression coverage for token issuance, cookie attributes, refresh rotation,
  blacklist behavior, logout, and unauthenticated `/me`.

Frontend tests must cover:

- API request methods, bodies, parsed field errors, Bearer header, and
  `credentials: "include"` where required;
- register success/failure states;
- verification pending/success/already-used/invalid/network states;
- login success, bad credentials, and unverified error;
- authenticated email-change success/validation/delivery-failure states and the
  immediate rendering of the new address as unverified;
- in-memory token use, `/me` rendering, one startup refresh attempt, failed
  refresh cleanup, and logout cleanup;
- no persistent token storage calls.

Run the existing backend pytest suite and frontend Vitest, lint, and build checks.
Do not weaken existing assertions or replace PostgreSQL-dependent tests with
SQLite-only coverage.

## 10. Manual acceptance-test checklist

Use local Compose and the console email backend. A developer unfamiliar with the
tests must be able to follow only these steps:

- [ ] Start the documented local stack and migrations with verification
  enforcement enabled.
- [ ] Open the frontend register page and submit a new username/email/password.
- [ ] See a clear check-your-email result and no authenticated state.
- [ ] Copy the verification URL from backend logs and open it in the browser.
- [ ] See verification success; reopening the same URL shows already verified.
- [ ] Attempting a tampered/expired URL shows a safe actionable error.
- [ ] Before verification, login is rejected when enforcement is enabled and no
  refresh cookie is created.
- [ ] After verification, login succeeds and the refresh cookie is HttpOnly,
  appropriately Secure for the environment, `SameSite=Strict`, and scoped to
  `/api/auth/`.
- [ ] The authenticated view loads `/api/auth/me/` and shows the expected user,
  email, and verified state.
- [ ] Reloading restores the session through one cookie refresh without browser
  token storage.
- [ ] Logout clears the UI state and refresh cookie; `/me` is no longer available
  without a new login.
- [ ] Duplicate username/email, weak password, bad credentials, missing email,
  and unavailable backend show clear errors.
- [ ] While authenticated as a verified user, change to a different available
  email address and see `/me` immediately show that new address as unverified.
- [ ] Confirm the old verification link/token no longer works after the change.
- [ ] Confirm a verification message is sent only to the new address; resending
  using the old address does not target or disclose the account.
- [ ] Open the new link and confirm the new address verifies successfully and
  `/me` now reports it as verified.
- [ ] With enforcement enabled, log out before verifying the changed address and
  confirm login is blocked with no refresh cookie; after verification, confirm
  login succeeds. With enforcement disabled, confirm login is allowed but `/me`
  remains unverified until the new address is verified.

## 11. Explicit out of scope

- TOTP MFA or any other MFA
- phone verification
- password reset/recovery
- OAuth 2.0, OIDC, social login, or external identity providers
- a Backend-for-Frontend (BFF)
- multiple simultaneous addresses per account or address history UI
- HTML email design, provider selection, deliverability analytics, or polished UI
- a general concurrent refresh queue/interceptor architecture
- unrelated catalog, orders, checkout, payment, or other commerce-domain changes

## 12. Migration and data-model considerations

The stock Django `User` is sufficient for this slice. Do **not** replace it.
Changing `AUTH_USER_MODEL` after auth tables, foreign keys, and SimpleJWT
blacklist migrations exist is a high-risk project-wide migration that is not
justified by email verification alone.

Add an accounts-owned one-to-one verification model with:

- primary key or opaque public identifier suitable for the verification URL;
- `user` one-to-one relation with cascade deletion;
- `normalized_email` with a database uniqueness constraint;
- nullable `verified_at`;
- nullable/blank token digest plus `token_created_at`/expiry information;
- `last_sent_at` for cooldown enforcement;
- ordinary created/updated timestamps if consistent with project conventions.

Keep `User.email` synchronized at registration, but treat the verification
record's normalized address as the verification authority for this slice. The
unique database constraint prevents concurrent duplicate reservations, which a
serializer-only check cannot guarantee. Provide a data migration for any
pre-existing users: create verification records deterministically, flag blank or
duplicate emails for operator review, and do not silently mark addresses verified
without an explicit documented policy. Keep enforcement off until that review is
complete.

All application writes to `User.email` in this slice must go through the
accounts-owned change operation so verification is invalidated atomically. The
model invariant is: `verified_at` applies if and only if the verification
record's normalized address equals the current normalized `User.email`. Direct
admin or shell edits can bypass application invariants, so either route admin
email edits through the same operation or make the field read-only there and
document the operator procedure. Do not use a fragile save signal as the primary
workflow; the service and database constraints must make the transition
explicit and testable.

A future custom-user migration may be reconsidered before broader profile,
multi-email, organization, or identity-provider work. If those requirements make
it necessary, write a separate migration plan covering table ownership, foreign
keys, permissions, admin, token relations, rollback, and production data; do not
smuggle that migration into this implementation.

## Completion boundary

The assignment is complete when all automated checks pass and the console-email
manual journey succeeds end to end. Do not expand the slice merely because a
broader account system might eventually need more capabilities.
