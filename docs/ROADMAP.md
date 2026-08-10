# Commerce Architect Roadmap

## Purpose

This is the living, high-level implementation roadmap for Commerce Architect.
Architecture documents describe the intended system and its constraints. This
roadmap describes the current implementation state and the major slices of work
that come next. GitHub issues define the detailed tasks and acceptance criteria.

```text
Architecture
    ↓
Roadmap
    ↓
GitHub Issues
    ↓
Code / Tests / Pull Requests
```

Update this roadmap when meaningful capabilities are completed or priorities
materially change. Do not use it as a duplicate backlog.

## Current State

```text
                    CURRENT STATE

                        Browser
                           │
                           │
                    React / Vite
                           │
                           │
              ┌────────────┴────────────┐
              │                         │
      Product UI works             Auth UI missing
              │                         X
              │
      GET /api/products/
              │
              ▼
          Django / DRF
              │
      ┌───────┴─────────────────────┐
      │                             │
   catalog                        accounts
      │                             │
products API              register  ✅
                          login     ✅
                          refresh   ✅
                          logout    ✅
                          /me       ✅
```

The catalog has an end-to-end vertical slice that is visible in the browser.
The authentication backend API exists and is tested, but the React frontend has
not yet been connected to those endpoints. Authentication is therefore a
backend capability today, not yet a complete user-facing experience.

## Current Major Capabilities

### Backend / Platform

- Django
- Django REST Framework
- PostgreSQL
- Containerized local development and CI environment
- Catalog/product API
- Accounts/authentication API
- SimpleJWT-based access/refresh lifecycle
- Backend pytest coverage
- GitHub Actions CI

### Frontend

- React
- TypeScript
- Vite
- Vitest
- React Testing Library
- Product listing UI
- API integration for products
- Authentication UI and state not yet implemented

## Authentication Focus

Authentication and the broader account lifecycle are the current major
implementation focus. The existing backend foundation includes:

- Registration endpoint
- Login/token endpoint
- Short-lived JWT access token
- HttpOnly refresh-token cookie
- Refresh rotation and blacklisting
- Logout
- Authenticated `/api/auth/me/` endpoint

The major incomplete areas are:

- Password-policy hardening
- Frontend authentication and session state
- Automatic access-token refresh behavior
- Email verification
- Password reset and recovery
- MFA
- Production security configuration
- Guest-to-account lifecycle

The broader account and authentication architecture remains under active
assessment. That assessment includes whether django-allauth or another mature
Django-native solution should provide portions of the account lifecycle. This
roadmap does not decide whether the current SimpleJWT approach will be retained
or replaced; that decision must follow the architectural assessment.

## Near-Term Roadmap

Three foundational workstreams are active in parallel. The capabilities listed
as future work are targets and do not describe current repository behavior.

### Authentication / Account Architecture

- Assess and settle account-lifecycle responsibilities and token/session
  strategy before building additional user-facing authentication work.
- Complete backend account-lifecycle and security capabilities, beginning with
  password-policy hardening tracked in
  [issue #4](https://github.com/anthonylpeterson/commerce-architect/issues/4),
  followed by the selected email verification, recovery, and lifecycle support.
- Connect React to authentication and session state. The primary frontend slice
  is tracked in
  [issue #5](https://github.com/anthonylpeterson/commerce-architect/issues/5),
  with concurrent refresh coordination tracked separately in
  [issue #6](https://github.com/anthonylpeterson/commerce-architect/issues/6).
- Complete coherent registration, login, logout, recovery, and verification
  flows, then add the selected MFA and stronger account-security capabilities.

### Developer + Adopter Experience

- **IN PROGRESS:** Move the Django/DRF backend from the repository root into
  `backend/`, making it a sibling of `frontend/`. This is a structural refactor
  only: runtime behavior, APIs, Compose, CI, database behavior, tests, and
  frontend behavior must remain unchanged. The boundary also prepares the
  project for future component-specific licensing and possible repository
  extraction.
- Establish a repeatable local development workflow and document it in a future
  `DEV_WORKFLOW.md`.
- Introduce a small task command surface, potentially including `dev-up`,
  `dev-down`, `dev-status`, `logs`, and `test`, without obscuring the underlying
  operations.
- Reduce developer onboarding friction while keeping setup reproducible and
  understandable.
- Define the production adoption and bootstrap workflow.
- Progressively automate configuration, deployment, domain and TLS setup,
  health verification, and operational startup where appropriate.

These workflow documents and commands are planned; they do not exist as a
standardized experience today.

### Public Repository Readiness

Public repository readiness is a top near-term priority, not a post-product
cleanup task. This workstream includes:

- A full repository and history secret/privacy audit
- A licensing decision
- `CONTRIBUTING.md`
- `SECURITY.md`
- Accurate public-facing maturity and status language
- Issue and contributor hygiene
- A final repository visibility review

### Continuing Product and Production Work

- Return to orders, checkout, payments, and the guest-to-account flow
  represented by
  [issue #9](https://github.com/anthonylpeterson/commerce-architect/issues/9).
- Harden production deployment and security. Production Django settings are
  tracked in
  [issue #7](https://github.com/anthonylpeterson/commerce-architect/issues/7),
  and deterministic Python builds in
  [issue #8](https://github.com/anthonylpeterson/commerce-architect/issues/8).

These issues are the source of detailed scope and acceptance criteria; the
roadmap records only how they fit into the larger implementation sequence.

## Future Commerce Work

Authentication is foundational work, not the platform's ultimate product goal.
Once the identity and account foundation is sufficiently complete, development
should return to broader commerce capabilities, including:

- Orders domain
- Checkout
- Payments
- Guest checkout
- Customer and order association
- Additional catalog capabilities as required

The detailed design and sequencing of these areas will be defined when they
enter active development. This roadmap does not resolve or alter existing
orders-domain feature work.

## Updating This Roadmap

ROADMAP.md is a living document, but it should not change for every small commit.
Update it when:

- A major vertical slice is completed.
- The next major development focus changes.
- An architectural assessment materially changes the planned direction.
- A significant capability moves from planned to implemented.
- New major domains enter active development.

GitHub issues remain the source of truth for detailed task scope and acceptance
criteria. Keep this roadmap concise enough that a developer returning after
months away can quickly understand what exists, what users can see, what remains
backend-only, what is currently being worked on, and which major area comes
next.
