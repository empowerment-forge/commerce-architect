
# UX_ARCHITECTURE.md
Version: 1.0
Status: Strategic Commitment Document

---

# 1. Purpose

This document defines the long-term UX and frontend architectural direction for the Commerce Platform.

It formalizes:

- Frontend technology decisions
- Backend interaction model
- Authentication UX strategy (Phase 1 and Phase 2 evolution)
- Architectural guardrails

This document is strategic and long-term.
It is NOT screen-specific.

---

# 2. Frontend Technology Commitment

We are formally committing to:

- React (SPA architecture)
- Vite (build tool)
- TypeScript (strict mode)
- Tailwind CSS (utility-first styling)
- Django REST Framework (API-only backend)
- PostgreSQL (data tier)

We are NOT using:

- HTMX
- Server-side rendered Django templates for customer UX
- Next.js
- Redux (Phase 1)
- SSR

This decision is long-term and intentional.
We will not switch paradigms in Phase 2.

---

# 3. System Model

Browser
   ↓
React SPA
   ↓
Django REST API (/api/*)
   ↓
PostgreSQL

Django is authoritative for:
- Business rules
- Data validation
- Security
- Authentication
- Authorization

React is responsible for:
- Rendering
- State management (UI-only)
- API consumption

---

# 4. Authentication Architecture

## Phase 1 (Current)

Authentication model:
- JWT-based authentication
- SimpleJWT
- Access + Refresh tokens
- Refresh rotation enabled
- Blacklisting enabled

Flow:
- User registers via /api/auth/register/
- User obtains token via /api/auth/token/
- Access token used in Authorization header:
  Bearer <token>

This is a backend-controlled token model.

Frontend responsibility:
- Store tokens securely (in memory preferred)
- Attach Authorization header to API calls
- Handle refresh rotation
- Handle 401 responses gracefully

---

## Phase 2 (Planned Evolution)

Authentication will evolve to:

Authorization Code Flow with PKCE
OAuth 2.0 + OpenID Connect compliant

Possible approaches:
- Django OAuth Toolkit
- External IdP (Auth0, Keycloak, etc.)
- Dedicated authorization server

Phase 2 Goals:
- Standards compliance
- Third-party integrations
- Social login support
- POS and mobile client compatibility

The Phase 1 JWT architecture is designed to evolve cleanly into this model.

---

# 5. UX Philosophy

The frontend must be:

- Minimal
- Professional
- Mobile-first
- API-driven
- Cleanly typed (TypeScript)

Avoid:
- Business logic in frontend
- Price math in frontend
- Security decisions in frontend
- Overengineering

---

# 6. Design Principles

- Utility-first styling (Tailwind)
- Restrained animation
- Neutral palette
- High readability
- Clear call-to-action hierarchy

We are building a commercial-grade foundation.

---

# 7. Guardrails

Do NOT introduce:

- Multiple frontend paradigms
- Mixed rendering strategies
- Uncontrolled global state
- UI libraries that abstract too much
- Server-side template fallback

Maintain architectural purity.

---

Approved Direction:
React + Vite + TypeScript + Tailwind
Django API-only
JWT (Phase 1) → OAuth2 PKCE (Phase 2)
Clean separation of concerns
Commercial-grade foundation
