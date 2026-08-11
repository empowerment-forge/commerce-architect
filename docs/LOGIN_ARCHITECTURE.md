# LOGIN_ARCHITECTURE.md

## Overview

This document defines the authentication architecture for the Commerce Architect platform.

We are implementing a secure hybrid JWT strategy that balances strong security with modern UX expectations.

---

# Phase 1 – Hybrid JWT Authentication

## Token Strategy

### Access Token
- Short-lived (10 minutes)
- Returned in JSON response on login
- Stored in memory only (React state/context)
- Sent via Authorization header:
  Authorization: Bearer <access_token>

### Refresh Token
- Long-lived (7 days)
- Stored in HttpOnly, Secure, SameSite=Strict cookie
- NOT accessible to JavaScript
- Automatically sent to:
  /api/auth/refresh/

---

## Authentication Flow

1. User logs in
2. Backend:
   - Returns access token in JSON
   - Sets refresh token in HttpOnly cookie
3. Frontend stores access token in memory
4. When access expires:
   - Frontend calls /api/auth/refresh/
   - Browser sends refresh cookie automatically
   - Backend rotates refresh token
   - Old token is blacklisted
   - New refresh cookie is set
   - New access token returned

---

## Security Controls

- ROTATE_REFRESH_TOKENS = True
- BLACKLIST_AFTER_ROTATION = True
- UPDATE_LAST_LOGIN = True
- HttpOnly refresh cookie
- Secure cookie (HTTPS in production)
- SameSite=Strict

---

# Business Model Decision

## Checkout Policy

We will follow modern ecommerce best practices:

- Guest checkout allowed
- Account creation encouraged
- Account auto-created after purchase
- JWT session issued after purchase

Order history requires login.

This maximizes conversion while preserving long-term customer retention.

---

# Phase 2 – OAuth2 Authorization Code Flow + PKCE

In Phase 2, authentication will evolve to:

- OAuth2 Authorization Code Flow with PKCE
- External Identity Provider compatibility
- OpenID Connect support
- MFA readiness

The current JWT implementation is designed to transition cleanly into this model.

---

# Architectural Principles

- No localStorage for refresh tokens
- No session-based auth
- No cookies accessible via JavaScript
- Stateless backend APIs
- Secure by default
- Test coverage required for all auth flows

---

End of Document
