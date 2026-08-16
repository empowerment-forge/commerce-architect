# User Authentication Architecture

## Overview

Commerce Architect currently uses a hybrid JWT authentication model for its
first-party API clients. Short-lived access tokens travel in JSON and
`Authorization` headers, while longer-lived refresh tokens remain in secure,
HttpOnly cookies.

This design supports the current React SPA without exposing refresh tokens to
frontend JavaScript. Authentication remains separate from commerce domain logic
so the platform can evolve to OAuth 2.0 Authorization Code with PKCE and OpenID
Connect in a later phase.

------------------------------------------------------------------------

# Phase 1 -- Hybrid JWT Authentication (Current Implementation)

## Technology Stack

-   Django and Django REST Framework (DRF)
-   `djangorestframework-simplejwt`
-   Simple JWT token blacklisting
-   PostgreSQL
-   Containerized local environment
-   Pytest backend test coverage
-   GitHub Actions CI

## Endpoints

All current authentication routes are mounted under `/api/auth/`:

-   `POST /api/auth/register/` creates a user and returns the new user's ID,
    username, normalized email, and unverified status. It validates the password,
    sends a verification email, and does not issue tokens.
-   `POST /api/auth/verify-email/` consumes an expiring, single-use token and
    verifies the exact normalized address to which it was issued.
-   `POST /api/auth/resend-verification/` returns an enumeration-resistant
    response for known, unknown, verified, and cooldown-limited addresses and,
    when eligible, rotates the token for the current address.
-   `POST /api/auth/resend-verification-authenticated/` derives the address
    from the authenticated user, applies the same cooldown and token rotation,
    and explicitly reports sent, cooldown, verified, or delivery-failure states.
-   `POST /api/auth/change-email/` requires JWT authentication, changes the
    current address, invalidates prior verification/tokens, and sends a new link.
-   `POST /api/auth/password-reset/request/` returns the same 202 response for
    every syntactically valid request and emails eligible verified accounts.
-   `POST /api/auth/password-reset/confirm/` validates a one-time recovery token
    and Django password policy, changes the password, revokes long-lived
    sessions, and requires a normal login afterward.
-   `POST /api/auth/token/` validates credentials, returns an access token in
    JSON, and sets the refresh token cookie.
-   `POST /api/auth/refresh/` reads the refresh token from its cookie, returns a
    new access token in JSON, and rotates the refresh token cookie when a new
    refresh token is issued.
-   `POST /api/auth/logout/` blacklists a valid refresh token when present and
    clears the refresh token cookie.
-   `GET /api/auth/me/` requires JWT authentication and returns the authenticated
    user's ID, username, current email, and matching verification metadata.

There is no `/api/auth/login/` endpoint. Login and initial token issuance use
`POST /api/auth/token/`.

## Email Verification

The stock Django `User` remains the account model. `accounts.EmailVerification`
owns a one-to-one verification record with a unique normalized email,
`verified_at`, token digest/timestamps, and resend state. Raw random tokens are
sent by email but never stored. Tokens expire, are single-use, and are valid only
while bound to both the record and current normalized `User.email`.

Changing email atomically clears `verified_at`, replaces the token, and requires
the new address to verify independently. Old-address links cannot verify the
account, and resend targets only the current address. Existing JWT sessions are
not automatically revoked by an address change; `/me` immediately reports the
new address as unverified.

`AUTH_REQUIRE_VERIFIED_EMAIL` controls credential-login enforcement. It defaults
to false for migration compatibility, while local Compose enables it for the
complete manual journey. When enabled, correct credentials for an unverified
current address return 403 without issuing a refresh cookie.

Local development defaults to the readable console email backend. For real-mail
UAT and production, the same `send_mail()` path can use any standards-compatible
SMTP provider through Django 6.1 `MAILERS` options supplied by environment
variables. The application has no provider SDK dependency. Verification links
open the frontend `/verify-email` page, which removes the raw query token from
browser history and submits verification by POST.

## Password Recovery and Account Security State

`accounts.PasswordRecoveryState` owns only recovery lifecycle data: a public
UUID, current normalized-email binding, random-token digest, issue/send times,
consumption time, and timestamps. Raw tokens have at least 256 bits of entropy,
are sent only by email, expire after 30 minutes by default, and are never
persisted. Reissue replaces the digest; successful consumption is single-use
and atomic. Failed delivery conditionally clears its issued digest and restores
the prior cooldown, permitting an immediate retry without changing the public
response.

`accounts.AccountSecurityState` separately owns the account-wide
`session_generation` counter. Login places the current generation on the token
pair. Cookie refresh compares it with current database state; missing claims and
absent rows mean generation zero for rollout compatibility. Recovery increments
the generation and blacklists outstanding refresh tokens, rejecting older
long-lived sessions, including refreshes rotated around reset. Already-issued
access tokens remain stateless for only their existing ten-minute maximum.

Recovery targets only an address matching both `User.email` and verified
`EmailVerification.normalized_email`. Email change invalidates recovery state;
the password-hash-bound digest also invalidates a link after any external
password change. Direct/admin password changes do not yet increment session
generation; that broader revocation belongs to a later account-security slice.

## Access Token

-   Lifetime: 10 minutes
-   Returned to the client as the `access` property in a JSON response
-   Intended to be held in frontend memory only
-   Sent on authenticated API requests as:

    ```text
    Authorization: Bearer <access_token>
    ```

-   Validated by DRF's Simple JWT authentication class

The access token is not placed in a cookie by the current backend.

## Refresh Token Cookie

-   Lifetime: 7 days
-   Cookie name: `refresh_token`
-   `HttpOnly`: enabled, so frontend JavaScript cannot read the token
-   `Secure`: disabled only for `COMMERCE_ENV=development` so local HTTP works;
    always enabled in production
-   `SameSite`: `Strict`
-   Path: `/api/auth/`, limiting the cookie to authentication endpoints

The refresh token is not returned in response JSON. The browser manages the
cookie and sends it to the refresh and logout endpoints when the request meets
the cookie's security and path rules.

The current Vite development proxy makes browser `/api` requests same-origin,
so no permissive CORS policy is required. `SameSite=Strict` is retained as a
strong CSRF boundary for the refresh cookie. Hosted development currently routes
the browser and API through a same-origin HTTPS boundary; any future
separate-origin or cross-site deployment requires explicit CORS and CSRF review
rather than weakening the cookie by default.

## Rotation, Blacklisting, and Logout

Refresh token rotation is enabled. After a successful refresh, Simple JWT can
issue a replacement refresh token, and the backend replaces the cookie with that
token. `BLACKLIST_AFTER_ROTATION` is enabled, so the old refresh token is
blacklisted after rotation.

Logout reads the refresh token cookie, attempts to blacklist that token, and
clears the cookie at `/api/auth/`. Logout also succeeds when the cookie is absent
or already invalid, allowing the client to finish local logout state cleanup.

Because rotation and logout use the Simple JWT blacklist application, refresh
token lifecycle state is maintained server-side. Access-token validation itself
continues to use signed JWT authentication.

## Current Request Flow

1.  The user submits credentials to `POST /api/auth/token/`.
2.  Django validates the credentials.
3.  Django returns the 10-minute access token in JSON and sets the 7-day
    HttpOnly refresh token cookie. It is `Secure` in production and local-HTTP
    compatible in development.
4.  The frontend retains the access token in memory and sends it in the Bearer
    authorization header for protected requests such as `GET /api/auth/me/`.
5.  When a new access token is needed, the frontend calls
    `POST /api/auth/refresh/`; the backend reads and validates the cookie.
6.  The backend returns a new access token and rotates the refresh token cookie.
7.  On logout, `POST /api/auth/logout/` blacklists the refresh token and clears
    the cookie.

## Testing

Backend authentication tests run in the `web` container. With Docker Compose:

```bash
docker compose exec -T web pytest
```

With Podman, run the test command directly in the existing container:

```bash
podman exec -i commerce_web pytest
```

GitHub Actions runs these tests against the validated production backend image
with disposable PostgreSQL. Compose remains the supported local orchestration
workflow; [DOCKER_SETUP.md](DOCKER_SETUP.md) defines the safe execution
convention.

## Deployment Topology and BFF Evolution

Commerce Architect is committed to a first-party SPA/PWA frontend while
preserving the ability to deploy that frontend independently from the commerce
API. Deployment independence does not necessarily mean cross-site deployment.
For example, `https://app.example.com` and `https://api.example.com` are
different origins, but remain same-site because they use HTTPS and share the
same registrable domain. By contrast,
`https://frontend-host.example-provider.com` and
`https://backend-host.other-provider.com` are genuinely cross-site and introduce
additional cookie, CORS, and CSRF constraints.

The current direct React SPA-to-Django/DRF authentication model remains
acceptable for Phase 1 while the frontend and API operate in an appropriate
same-site topology:

```text
React SPA / PWA
      |
      | access JWT + secure refresh cookie
      v
Django / DRF
```

The architecture must not require `SameSite=None` cross-site authentication as
a foundational assumption merely to accommodate a future hosting arrangement.
If the browser frontend and commerce APIs are later hosted on genuinely
different sites, a Backend-for-Frontend (BFF) should be considered as the
preferred browser-facing security boundary before weakening cookie SameSite
policy:

```text
Browser SPA / PWA
      |
      | same-site secure session
      v
Browser-facing BFF
      |
      | server-to-server authentication
      v
Django / Commerce APIs
```

Under such a model, the browser could authenticate only with secure, HttpOnly
session cookies while JWT or OAuth credentials remain behind the
browser-facing boundary. Frontend authentication code should therefore avoid
unnecessarily coupling React components to JWT mechanics, allowing session
ownership to evolve without widespread frontend rewrites.

This is an architectural constraint and future option, not a decision to
implement a BFF or introduce another deployable service now. The guiding
principle is to preserve strong browser cookie isolation and deployment
flexibility by preferring an appropriate browser-facing security boundary over
relaxing cookie policy solely for cross-site hosting. It does not assert that
`SameSite=Strict` is suitable for every possible topology.

------------------------------------------------------------------------

# Phase 2 -- OAuth 2.0 Authorization Code with PKCE and OIDC

## Motivation

The planned evolution supports:

-   Multiple client types, including SPAs, mobile apps, and POS devices
-   Delegated authorization flows
-   Potential third-party integrations
-   Separation of authorization-server and resource-server responsibilities
-   OpenID Connect identity capabilities

## Target Standards

-   OAuth 2.0 Authorization Code Flow
-   PKCE (Proof Key for Code Exchange)
-   OpenID Connect (OIDC)
-   Short-lived access tokens
-   Secure refresh-token rotation

PKCE protects public clients against authorization-code interception without
requiring a client secret in browser or mobile applications.

## Migration Direction

Phase 2 is expected to introduce standards-based authorization endpoints,
migrate first-party clients from direct credential submission to redirect-based
authorization, and expand authentication tests. The precise server and endpoint
design will be established when that phase is implemented.

The current separation between authentication and commerce domain logic is
intended to allow that evolution without rewriting the catalog and other business
domains.

------------------------------------------------------------------------

# Summary

Phase 1 uses short-lived JWT access tokens in frontend memory plus rotating
refresh tokens in secure, HttpOnly cookies. Phase 2 preserves the architectural
direction toward OAuth 2.0 Authorization Code with PKCE and OpenID Connect.
