
# TESTING_STRATEGY.md
Version: 1.0
Status: Active Testing Doctrine

---

# 1. Purpose

This document defines the full testing strategy for the Commerce Platform.

It covers:

- Backend API testing (pytest + Django)
- Authentication testing
- React component testing
- React integration testing
- End-to-end (E2E) testing
- CI integration
- Codex-driven test generation standards

This is the single source of truth for how we ensure quality.

---

# 2. Core Testing Philosophy

We enforce the following principles:

1. Test behavior, not implementation details.
2. Keep business logic in the backend — test it there.
3. Keep frontend logic minimal — test rendering and state transitions.
4. Protect contracts (API shape must remain stable).
5. Fail fast in CI.
6. Never weaken tests to “make them pass.” Fix the root cause.

---

# 3. Backend Testing (Django + Pytest)

## 3.1 Framework

- pytest
- pytest-django
- Django TestClient
- SimpleJWT auth tests

All backend tests run inside Docker:

docker compose exec -T web pytest

CI executes this automatically.

---

## 3.2 What We Test

### Model Tests
- Decimal precision for price
- Field constraints
- Default values
- Business rules normalization

### API Tests
- GET /api/products
- Auth-protected endpoints
- JWT issuance
- Refresh rotation
- Blacklist enforcement

### Health Endpoint
- Returns 200
- Database connectivity validated

---

# 4. Frontend Testing Strategy (React + Vite + TypeScript + Tailwind)

Frontend testing is layered.

---

## 4.1 Unit Testing (Component-Level)

Tools:
- Vitest or Jest
- React Testing Library
- @testing-library/jest-dom

What we test:

ProductCard:
- Renders name
- Renders price
- Truncates description
- No crashes with valid props

ProductListPage:
- Loading state renders
- Error state renders
- Products render correctly

Rules:
- No CSS class assertions
- Test by role, text, or accessible selectors
- Mock API responses

---

## 4.2 Integration Testing (UI + API Layer)

Tools:
- React Testing Library
- MSW (Mock Service Worker)

What we test:
- API success → grid renders
- API failure → error shown
- Empty response → empty state shown

MSW simulates:
GET /api/products/

No real backend required for these tests.

---

## 4.3 End-to-End (E2E) Testing

Tools:
- Playwright (preferred)
- Cypress (alternative)

Scope:
- Login flow
- Token storage behavior
- Product listing renders
- Mobile responsiveness
- Auth-protected routes redirect correctly

These tests use real Django + real frontend build.

---

# 5. CI Integration

Backend tests already run in CI:

- Build Docker
- Start services
- Run pytest

Frontend tests will be added:

Example CI additions:

- name: Install frontend dependencies
  run: npm ci --prefix frontend

- name: Run frontend unit tests
  run: npm run test --prefix frontend

- name: Run E2E tests
  run: npm run e2e --prefix frontend

CI must fail if any layer fails.

---

# 6. Testing Evolution Plan

Phase 1:
- Backend fully tested
- Frontend unit + integration tests

Phase 2:
- E2E mandatory
- Auth Code + PKCE flows tested
- Role-based UI tested

---

# 7. Codex Prompt Template for Frontend Testing

Use the following prompt when generating frontend tests:

------------------------------------------------------------

You are an AI assistant modifying the repository directly.

Objective:
Implement a full frontend testing suite for the React SPA.

Requirements:

1. Install and configure:
   - Vitest (or Jest)
   - React Testing Library
   - @testing-library/jest-dom
   - MSW for API mocking

2. Create tests for:

   ProductCard:
   - Renders name
   - Renders price
   - Truncates description correctly

   ProductListPage:
   - Shows loading state
   - Shows error state on failed API
   - Renders products on success

3. Mock GET /api/products using MSW.

4. Ensure tests run with:
   npm run test

5. Do NOT modify backend code.
6. Do NOT alter business logic.
7. Output summary of files created.
8. Do not commit automatically.

------------------------------------------------------------

---

# 8. Quality Standard

Before merging any feature branch:

- Backend pytest passes
- Frontend tests pass
- No console warnings
- CI passes

Quality gates are mandatory.

---

# 9. Definition of Done (Testing Perspective)

A feature is complete when:

- Business logic validated
- API contract verified
- UI state transitions tested
- CI pipeline green
- No weakened tests

---

This document defines how we protect quality as the platform scales.

Testing is not optional.
Testing is part of the architecture.
