
# Frontend and UX Architecture

**Status:** Current strategic direction. For implemented runtime topology and
authentication details, see [ARCHITECTURE.md](ARCHITECTURE.md) and
[USERAUTH_ARCHITECTURE.md](USERAUTH_ARCHITECTURE.md).

---

# 1. Purpose

This document defines the long-term UX and frontend architectural direction for
Commerce Architect.

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

# 4. Authentication Boundary

The frontend holds short-lived access tokens only in memory and leaves rotating
refresh tokens in secure HttpOnly cookies. It attaches authorization headers,
coordinates refresh/retry, and renders account journeys without owning identity
or security decisions. The backend owns credentials, token lifecycle,
verification, recovery, and authorization.

[USERAUTH_ARCHITECTURE.md](USERAUTH_ARCHITECTURE.md) is the canonical source for
the implemented endpoints, security properties, and possible OAuth 2.0/OIDC
evolution.

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

Current direction:
React + Vite + TypeScript + Tailwind
Django API-only
JWT (Phase 1) → OAuth2 PKCE (Phase 2)
Clean separation of concerns
Commercial-grade foundation
