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
    username, and email. It does not issue tokens.
-   `POST /api/auth/token/` validates credentials, returns an access token in
    JSON, and sets the refresh token cookie.
-   `POST /api/auth/refresh/` reads the refresh token from its cookie, returns a
    new access token in JSON, and rotates the refresh token cookie when a new
    refresh token is issued.
-   `POST /api/auth/logout/` blacklists a valid refresh token when present and
    clears the refresh token cookie.
-   `GET /api/auth/me/` requires JWT authentication and returns the authenticated
    user's ID, username, and email.

There is no `/api/auth/login/` endpoint. Login and initial token issuance use
`POST /api/auth/token/`.

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
-   `Secure`: enabled, so the browser sends it only over a secure connection
-   `SameSite`: `Strict`
-   Path: `/api/auth/`, limiting the cookie to authentication endpoints

The refresh token is not returned in response JSON. The browser manages the
cookie and sends it to the refresh and logout endpoints when the request meets
the cookie's security and path rules.

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
3.  Django returns the 10-minute access token in JSON and sets the 7-day secure,
    HttpOnly refresh token cookie.
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

With Podman Compose, the local equivalent is:

```bash
podman-compose exec -T web pytest
```

GitHub Actions currently uses Docker Compose for CI.

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
