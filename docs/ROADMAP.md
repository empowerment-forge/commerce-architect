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
                          recovery  ✅
```

The catalog has an end-to-end vertical slice that is visible in the browser.
Authentication now has a complete first user-facing foundation: registration,
email verification and resend, login, `/me`, email change/reverification,
access-token refresh/retry, logout, and password recovery/reset are connected
through the React frontend. Recovery revokes account-wide refresh sessions, and
real SMTP delivery through Resend has passed deployed development acceptance.

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
- Authentication and account-management UI with in-memory access-token state
- Responsive Account actions across narrow and wider viewports

## Current Priority: Hosted-Development Operational Readiness

Commerce Architect is deployed at
[https://dev-commerce.empowerment-forge.com](https://dev-commerce.empowerment-forge.com)
as an internet-facing, production-style **non-production** Railway environment.
The current operational priority is making that working environment
reproducible and observable while retaining HTTPS, non-production credentials,
no real customer commerce data, and hardened Django runtime settings. The
environment is not carrying revenue-critical production workloads.

Operational hardening should progress deliberately alongside useful
business-domain modeling, design, and use-case exploration. Production
readiness remains required before real customer or revenue-critical workloads,
but every operational outcome is not a gate on continued exploration of
Orders, Inventory, Checkout, Payments, and related commerce domains.

The authoritative architecture and implementation guide for this milestone is
[BUILD_DEPLOY.md](BUILD_DEPLOY.md). This roadmap defines priority and milestone
outcomes; GitHub issues and that guide should hold detailed implementation
decisions and procedures.

### Deployment and operations milestone

The runtime topology, frontend/backend production artifacts, NGINX same-origin
routing, persistent private PostgreSQL, custom domain, HTTPS, migrations,
health gates, image validation/scanning, and digest deployments are complete.
Bare frontend proxy-prefix redirects are also covered against public leakage of
internal scheme or port details.

The practical priority order for the remaining operational-readiness work is:

1. Independently verify clean-environment provisioning and reproducibility.
2. Establish useful logging, health visibility, monitoring, and alerting
   without leaking sensitive data.
3. Complete OWASP-oriented application security validation and establish
   repeatable penetration/security testing for the internet-facing environment.
4. Establish and exercise application and database rollback procedures.
5. Define backup policy and successfully test database restoration.

Rollback and backup/restoration are required operational capabilities, not
optional work. Their urgency increases substantially before production use and
especially before revenue or customer data depends on the platform. Broader
launch, recovery, credential-rotation, incident-response, and sensitive-data
procedures remain part of the path from the current production-style
non-production environment to production readiness.

## Existing Authentication Foundation

**COMPLETE:** The independently testable user-facing foundation includes
registration, email verification and resend, authenticated email change and
reverification, hybrid-JWT login/logout and `/me`, access-token refresh/retry,
and password recovery/reset. Its registration and verification acceptance
contract is
[ai-prompts/auth-registration-verification.md](ai-prompts/auth-registration-verification.md).

Authentication and the broader account lifecycle remain important platform
work, especially where required to secure and validate the hosted environment.
Password recovery is governed by
[ai-prompts/auth-password-recovery.md](ai-prompts/auth-password-recovery.md) and
is complete at milestone `milestone/auth-password-recovery`, including real
Resend delivery, Railway acceptance, and
[13/13 UAT PASS](uat-testing/UAT_PASSWORD_RECOVERY.md).
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
- Frontend authentication, recovery, and account-management UI
- Enumeration-resistant, expiring, single-use password recovery with cooldowns
- Account-wide session-generation revocation after password reset

The major incomplete areas are:

- Broader password/account policy hardening
- Broader adoption of the implemented single-flight access-token refresh/retry
  helper as future authenticated frontend operations are added
- MFA
- Further production-oriented account-security validation and hardening
- Guest-to-account lifecycle

The implemented slice retains Django's stock `User` with accounts-owned email
verification state. A custom-user migration is not justified now and would need
a separate risk-managed plan if broader identity requirements later demand it.

## Supporting Workstreams

These workstreams support operational readiness or future product development.
Capabilities listed as future work do not describe current repository behavior.

### Authentication / Account Architecture

- Preserve and extend the coherent registration, verification, login, logout,
  recovery, and account-management foundation as new authenticated operations
  are introduced.
- Continue broader password/account-policy hardening, then add selected MFA and
  stronger account-security capabilities through separately scoped work.
- Design the guest-to-account lifecycle with the future checkout and orders
  domains rather than treating the current identity foundation as permanently
  complete.

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
- Use the canonical
  [validation and PR reporting standard](VALIDATION_STANDARDS.md) to distinguish
  automated checks, CI, human/UAT, and deployed acceptance.
- Define the production adoption and bootstrap workflow.
- Progressively automate configuration, deployment, domain and TLS setup,
  health verification, and operational startup where appropriate.

The broader workflow documents and command surface remain planned; they do not
exist as a standardized experience today.

### Public Repository Readiness

Public repository readiness is a top near-term priority, not a post-product
cleanup task. The license map, contribution guide, security policy, and current
public-facing maturity language exist. Remaining work includes:

- A full repository and history secret/privacy audit
- Issue and contributor hygiene
- A final repository visibility review

### Product Work and Supporting Hardening

- Continue modeling and use-case exploration for orders, checkout, payments,
  and the guest-to-account flow represented by
  [issue #9](https://github.com/empowerment-forge/commerce-architect/issues/9).
- Sequence implementation responsibly alongside the prioritized operational
  hardening above; production use still requires the remaining readiness work.
- Continue production deployment and security hardening. Production Django
  settings are tracked in
  [issue #7](https://github.com/empowerment-forge/commerce-architect/issues/7),
  and deterministic Python builds in
  [issue #8](https://github.com/empowerment-forge/commerce-architect/issues/8).

These issues are the source of detailed scope and acceptance criteria; the
roadmap records only how they fit into the larger implementation sequence.

## Future Commerce Work

Deployment and authentication are foundational work, not the platform's
ultimate product goal. Business-domain modeling, design, and use-case work can
continue while operational hardening progresses. Implementation should return
deliberately to broader commerce capabilities, including:

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
