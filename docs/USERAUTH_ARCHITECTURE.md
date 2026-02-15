# USER AUTHENTICATION ARCHITECTURE

## Overview

This document defines the authentication architecture for the
Empowerment Forge Commerce Platform.

Authentication is implemented in **phases** to balance:

-   Security
-   Development velocity
-   Architectural cleanliness
-   Future extensibility

Phase 1 prioritizes secure, stateless API authentication using JWT.
Phase 2 evolves the system to full OAuth 2.0 Authorization Code Flow
with PKCE and OpenID Connect.

------------------------------------------------------------------------

# Phase 1 -- JWT-Based API Authentication (Current Implementation)

## Objectives

-   Stateless authentication
-   No session cookies for API access
-   SPA-ready
-   Mobile-ready
-   Secure by default
-   Minimal operational complexity
-   Fully testable via CI

## Technology Stack

-   Django
-   Django REST Framework (DRF)
-   djangorestframework-simplejwt
-   PostgreSQL
-   Dockerized environment
-   Pytest for test coverage
-   GitHub Actions for CI

## Authentication Model

### Token Issuance Flow

1.  User submits credentials (username/email + password) to:

    -   `POST /api/auth/login/`

2.  Backend validates credentials.

3.  Server returns:

    -   Access Token (short-lived)
    -   Refresh Token (longer-lived)

4.  Client stores tokens securely (frontend responsibility).

5.  All authenticated requests include:

    Authorization: Bearer `<access_token>`{=html}

### Token Type

-   JWT (JSON Web Token)
-   Signed server-side
-   No server-side session storage
-   Fully stateless verification

## Security Characteristics

-   No server sessions
-   No cookie-based authentication for APIs
-   CSRF not required for token-based API
-   Access token expiration enforced
-   Refresh token rotation configurable
-   Password hashing via Django (PBKDF2 by default)

## Endpoints (Phase 1)

-   POST /api/auth/register/
-   POST /api/auth/login/
-   POST /api/auth/refresh/
-   GET /api/auth/me/

## Testing Strategy (Phase 1)

Tests include:

-   User registration success/failure
-   Login success/failure
-   Token refresh
-   Protected endpoint access
-   Unauthorized access rejection
-   Token expiry behavior (future enhancement)

All tests run inside Docker via:

    docker compose exec -T web pytest

CI executes tests automatically on merge events.

------------------------------------------------------------------------

# Architectural Tradeoffs (Phase 1)

Why not OAuth 2.0 + PKCE now?

Because Phase 1 focuses on:

-   First-party clients only
-   Rapid iteration
-   Controlled environment
-   Minimal moving parts

JWT authentication via simplejwt provides:

-   Production-ready security
-   Clean upgrade path
-   No architectural dead ends

It is intentionally chosen as a pragmatic foundation.

------------------------------------------------------------------------

# Phase 2 -- Evolution to OAuth 2.0 Authorization Code Flow with PKCE

## Motivation

Phase 2 will introduce:

-   Multiple client types (SPA, mobile apps, POS devices)
-   Delegated authentication flows
-   Potential third-party integrations
-   Stronger separation of Authorization Server and Resource Server
-   OpenID Connect compliance

## Target Standard

-   OAuth 2.0 Authorization Code Flow
-   PKCE (Proof Key for Code Exchange)
-   OpenID Connect (OIDC)
-   Short-lived access tokens
-   Rotating refresh tokens

## High-Level Phase 2 Architecture

### Authorization Server Responsibilities

-   /oauth/authorize
-   /oauth/token
-   Client registration
-   PKCE challenge verification
-   State & nonce validation
-   ID token issuance (OIDC)

### Resource Server (API)

-   Verifies signed JWT access tokens
-   No session storage
-   No cookie dependency
-   Fine-grained scope enforcement

## Why PKCE?

PKCE ensures:

-   Secure public client authentication
-   Protection against authorization code interception
-   No need for client secret in SPA/mobile apps
-   Modern industry standard for OAuth implementations

## Migration Strategy

Phase 2 will:

1.  Introduce OAuth endpoints alongside existing JWT endpoints.
2.  Deprecate direct credential login endpoints.
3.  Migrate SPA to redirect-based authorization.
4.  Maintain backward compatibility during transition.
5.  Expand test suite to cover OAuth flows.

No core domain logic will require refactoring.

Authentication is intentionally decoupled from business logic to enable
this evolution.

------------------------------------------------------------------------

# Security Commitment

By launch time, the platform will:

-   Use industry-standard OAuth 2.0 Authorization Code Flow with PKCE
-   Follow OpenID Connect specifications
-   Enforce HTTPS everywhere
-   Use secure token lifetimes and rotation
-   Maintain automated CI test coverage
-   Avoid unnecessary cookie-based authentication

Phase 1 is secure and production-grade. Phase 2 elevates the system to
modern identity standards.

------------------------------------------------------------------------

# Summary

Phase 1: - JWT-based stateless API authentication - Rapid
implementation - Secure foundation

Phase 2: - OAuth 2.0 Authorization Code Flow - PKCE - OpenID Connect
compliance - Enterprise-grade identity model

This staged strategy balances speed with long-term architectural
integrity.
