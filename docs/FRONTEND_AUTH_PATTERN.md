# FRONTEND_AUTH_PATTERN.md

# Standard Frontend → Backend Auth Pattern (Hybrid JWT)

## Overview

This document defines the official authentication pattern for the React SPA
communicating with the Django REST backend.

This pattern is mandatory for all future frontend development.

---

# Architecture Summary

Hybrid JWT Strategy:

- Access Token:
  - Returned in JSON from /api/auth/token/
  - Stored in memory only (React state / auth store)
  - Short-lived (10 minutes)
  - Sent in Authorization header for protected endpoints

- Refresh Token:
  - Stored in HttpOnly, Secure cookie
  - Path restricted to /api/auth/ so refresh and logout can receive it
  - Rotated and blacklisted on refresh
  - Never accessible to JavaScript

---

# Login Flow

1. User submits credentials
2. POST /api/auth/token/
3. Backend:
   - Returns access token (JSON)
   - Sets refresh_token cookie
4. Frontend:
   - Stores access token in memory
   - Marks user as authenticated

---

# Authenticated API Calls

Frontend uses Axios interceptor:

- Reads access token from auth store
- Adds:
  Authorization: Bearer <access_token>

Django:
- Verifies JWT signature
- Extracts user_id
- Populates request.user

---

# Access Token Expiry Handling

When access token expires:

1. API call returns 401
2. Axios response interceptor triggers
3. Frontend calls:
   POST /api/auth/refresh/
4. Browser automatically sends refresh_token cookie
5. Backend:
   - Validates refresh token
   - Rotates refresh token
   - Returns new access token
6. Frontend:
   - Updates access token in memory
   - Retries original request

User remains logged in transparently.

---

# Logout Flow

Frontend calls:

POST /api/auth/logout/

Backend:
- Blacklists refresh token
- Clears refresh_token cookie

Frontend:
- Clears access token from memory
- Redirects to login page

---

# Security Properties

- No tokens stored in localStorage
- No tokens stored in non-HttpOnly cookies
- Access tokens are short-lived
- Refresh tokens are rotation-enabled and blacklisted
- Frontend never handles refresh token directly

---

# Phase 2 Evolution

Future improvements may include:

- Authorization Code Flow with PKCE
- External identity providers
- MFA enforcement
- Device/session management UI

This document defines Phase 1 standard.
