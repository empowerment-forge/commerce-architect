# Testing Strategy

## Purpose

This document defines the repository's current test layers and quality gates.
It describes what the maintained suites prove. Validation results in pull
requests follow [VALIDATION_STANDARDS.md](VALIDATION_STANDARDS.md).

## Principles

1. Test observable behavior and stable contracts, not implementation trivia.
2. Keep business rules in the backend and test them at that boundary.
3. Test frontend rendering, interaction, state transitions, and API-client
   behavior through accessible selectors.
4. Keep tests deterministic and fix root causes rather than weakening coverage.
5. Distinguish component evidence from real-browser, device, and deployed UAT.

## Backend

Pytest and pytest-django cover the real Django application with PostgreSQL.
Maintained coverage includes:

- product models and API behavior;
- database-aware health behavior;
- registration, verification, email change, login, refresh, logout, and `/me`;
- enumeration resistance, token lifecycle, password recovery, and session
  revocation;
- development/production security-setting boundaries.

Run the suite through the Compose backend service:

```bash
docker compose exec -T web pytest
```

Use `podman-compose` in the supported Podman workflow. CI runs pytest against
the validated production backend image with disposable PostgreSQL, then runs
Django system, deployment, migration, and runtime checks.

## Frontend

Vitest, React Testing Library, and jest-dom cover components, application
journeys, and the fetch-based API client. Maintained coverage includes product
states, authentication/account interactions, verification and recovery pages,
single-flight refresh/retry, and logout cleanup.

Tests use roles, labels, text, and accessible state where possible. jsdom can
verify DOM and interaction contracts, but it does not prove pixel layout,
responsive fit, browser networking, email delivery, or deployed behavior.
Those claims require the appropriate browser/device or environment acceptance.

Run the frontend checks through Compose or from `frontend/`:

```bash
npm run test -- --run
npm run lint
npm run build
```

## Production Images and Routing

CI builds each production image once and validates that exact artifact. The
frontend runtime checks cover SPA fallback, backend proxy behavior, safe
bare-prefix redirects, and dotfile rejection. The backend runtime checks cover
startup, database migrations, Django health, and deployment security settings.
Trivy scans both production images for fixed HIGH/CRITICAL findings.

Successful `develop` pushes publish and deploy validated images by immutable
digest, require public development smoke checks, and create an immutable
promotion record. Pull requests to `develop` validate without deployment.
`develop` to `main` release pull requests validate their pinned promotion
record; the merged release promotes those exact digests without rebuilding.
See [BUILD_DEPLOY.md](BUILD_DEPLOY.md) for the canonical trigger matrix.

## Human and End-to-End Acceptance

Browser end-to-end automation is not currently part of CI. Feature-specific
manual acceptance records live under `uat-testing/` where needed. Responsive
layout, real email delivery, browser history behavior, and post-deployment
journeys must not be claimed from component tests alone.

## Merge Standard

Before merge, run the checks relevant to the changed slice, confirm CI passes,
and report both important behavior and any remaining human-only verification.
Feature/task acceptance criteria still define the exact coverage required;
this document does not replace them.
