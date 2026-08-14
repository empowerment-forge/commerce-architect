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
      Product UI works             Auth UI works
              │                         │
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
                          verify    ✅
                          email change ✅
                          login     ✅
                          refresh   ✅
                          logout    ✅
                          /me       ✅
```

The catalog has an end-to-end vertical slice that is visible in the browser.
Authentication is now a complete first user-facing slice: registration, email
verification, login, `/me`, email change/reverification, refresh restoration,
and logout are connected through the React frontend.

## Current Major Capabilities

### Backend / Platform

- Django
- Django REST Framework
- PostgreSQL
- Containerized local development and production-image CI validation
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
- Minimal authentication UI and in-memory session state

## Current Priority: Hosted-Development Operational Readiness

Commerce Architect is deployed at
[https://dev-commerce.empowerment-forge.com](https://dev-commerce.empowerment-forge.com)
as an internet-facing, production-style **non-production** Railway environment.
The current priority is making that working environment reproducible and
recoverable while retaining HTTPS, non-production credentials, no real customer
data, and hardened Django runtime settings.

Additional commerce and business-domain development—including Orders,
Inventory, Checkout, and Payments—is temporarily secondary. Priority returns
to those domains only after the existing platform has been deployed securely,
tested, operated, recovered, and updated successfully in the development
deployment.

The authoritative architecture and implementation guide for this milestone is
[BUILD_DEPLOY.md](BUILD_DEPLOY.md). This roadmap defines priority and milestone
outcomes; GitHub issues and that guide should hold detailed implementation
decisions and procedures.

### Deployment and operations milestone

The runtime topology, frontend/backend production artifacts, NGINX same-origin
routing, persistent private PostgreSQL, custom domain, HTTPS, migrations,
health gates, image validation/scanning, and digest deployments are complete.

The broader operational-readiness milestone remains in progress until the team
has:

- Independently verified the documented clean-environment provisioning procedure.
- Completed post-deployment and real-HTTPS authentication checks.
- Established application and database rollback procedures.
- Established useful logging, health visibility, monitoring, and alerting
  without leaking sensitive data.
- Completed remaining static/security and dynamic application gates beyond the
  current dependency and container-image scanning.
- Established OWASP-oriented application security testing and a repeatable
  penetration-testing process for the internet-facing environment.
- Protected sensitive data in the database, logs, backups, and configuration.
- Defined backup policy and successfully tested restoration.
- Documented launch, deployment, rollback, recovery, credential rotation, and
  incident-oriented operational procedures.
- Demonstrated that the environment can be securely built, deployed, tested,
  operated, updated, rolled back, and recovered.

Only after these outcomes are met does priority return to Orders and other
business domains.

## Existing Authentication Foundation

**COMPLETE:** The independently testable registration, email verification and
reverification, hybrid-JWT login/logout and `/me`, and minimal React UI slice is
implemented. Its acceptance contract is
[ai-prompts/auth-registration-verification.md](ai-prompts/auth-registration-verification.md).

Authentication and the broader account lifecycle remain important platform
work, especially where required to secure and validate the hosted environment.
The existing backend foundation includes:

- Registration endpoint
- Email verification and enumeration-resistant resend
- Authenticated email change and reverification
- Login/token endpoint
- Short-lived JWT access token
- HttpOnly refresh-token cookie
- Refresh rotation and blacklisting
- Logout
- Authenticated `/api/auth/me/` endpoint
- Minimal frontend authentication/session UI

The major incomplete areas are:

- Broader password/account policy hardening
- Broader adoption of the implemented single-flight access-token refresh/retry
  helper as future authenticated frontend operations are added
- Password reset and recovery
- MFA
- Production security configuration
- Guest-to-account lifecycle

The implemented slice retains Django's stock `User` with accounts-owned email
verification state. A custom-user migration is not justified now and would need
a separate risk-managed plan if broader identity requirements later demand it.

## Supporting Workstreams

These workstreams support the deployment milestone or remain queued behind it.
Capabilities listed as future work do not describe current repository behavior.

### Authentication / Account Architecture

- Assess and settle account-lifecycle responsibilities and token/session
  strategy before building additional user-facing authentication work.
- Complete backend account-lifecycle and security capabilities, beginning with
  password-policy hardening tracked in
  [issue #4](https://github.com/empowerment-forge/commerce-architect/issues/4),
  followed by the selected email verification, recovery, and lifecycle support.
- Connect React to authentication and session state. The primary frontend slice
  is tracked in
  [issue #5](https://github.com/empowerment-forge/commerce-architect/issues/5),
  with concurrent refresh coordination tracked separately in
  [issue #6](https://github.com/empowerment-forge/commerce-architect/issues/6).
- Complete coherent registration, login, logout, recovery, and verification
  flows, then add the selected MFA and stronger account-security capabilities.

### Developer + Adopter Experience

- **COMPLETE:** The Django / DRF backend now lives under `backend/`, with
  `backend/` and `frontend/` as explicit sibling application boundaries. The
  refactor preserved runtime behavior, APIs, Compose topology, CI behavior,
  database state, tests, and frontend behavior. This structure prepares
  Commerce Architect for future component-specific licensing and possible
  repository extraction.
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

### Deferred Product Work and Supporting Hardening

- After the deployment milestone, return to orders, checkout, payments, and the
  guest-to-account flow represented by
  [issue #9](https://github.com/empowerment-forge/commerce-architect/issues/9).
- Harden production deployment and security. Production Django settings are
  tracked in
  [issue #7](https://github.com/empowerment-forge/commerce-architect/issues/7),
  and deterministic Python builds in
  [issue #8](https://github.com/empowerment-forge/commerce-architect/issues/8).

These issues are the source of detailed scope and acceptance criteria; the
roadmap records only how they fit into the larger implementation sequence.

## Future Commerce Work

Deployment and authentication are foundational work, not the platform's
ultimate product goal. Once the production-style development deployment
milestone is complete and the identity foundation is sufficient for its secure
operation, development should return to broader commerce capabilities,
including:

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
