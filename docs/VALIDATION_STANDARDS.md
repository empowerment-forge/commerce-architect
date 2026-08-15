# Validation and Pull Request Reporting Standards

## Purpose

This document defines the canonical validation and pull-request reporting
standard for Commerce Architect. It applies to human contributors,
AI-assisted development tools, and future maintainers.

Implementation pull requests should include a concise, standardized
`## Validation Summary`. The summary should answer:

- what was tested;
- what passed or failed;
- which important behaviors were covered; and
- what remains human/UAT-only, blocked, or otherwise unverified.

Detailed raw logs belong in GitHub Actions. Do not copy them into a pull-request
description unless a relevant excerpt is needed to explain a failure.

## Required Validation Summary

Every implementation pull request should use the following subsections
consistently when they apply. Omit a section only when it would be meaningless
for the change; otherwise state explicitly that the area was not changed.

### Backend

Report, as applicable:

- test count and result;
- important backend behaviors covered;
- Django system-check result;
- migration status, including when no migration was created;
- API or security behavior materially relevant to the change; and
- an explicit statement when backend behavior was not changed.

### Frontend

Report, as applicable:

- test count and result;
- important frontend behaviors covered;
- ESLint result;
- production build result;
- accessibility or interaction validation materially relevant to the change;
  and
- an explicit statement when frontend behavior was not changed.

### Infrastructure / Build

Report, as applicable:

- production image build validation;
- exact-image or runtime validation;
- NGINX, routing, or proxy checks;
- security scans;
- CI and required-check status;
- `git diff --check` result;
- relevant deployment validation; and
- an explicit statement when infrastructure was not affected.

### Human / UAT

Report, as applicable:

- manual acceptance performed;
- environment, device, and browser when relevant;
- `PASS`, `FAIL`, or `BLOCKED` status;
- post-deployment validation; and
- anything still requiring human verification.

## Reporting Rules

- Keep summaries concise and useful.
- Do not dump raw logs into pull-request descriptions.
- Do not list every individual test unless it materially explains coverage.
- Report important behavioral coverage, not merely test counts.
- Do not claim automated coverage for behavior verified only manually.
- Do not claim human acceptance for behavior verified only through automated
  tests.
- Do not treat jsdom or component rendering as proof of real pixel-layout
  behavior.
- Distinguish local validation from deployed acceptance.
- Distinguish CI success from UAT success.
- A blocked post-deployment UAT step is not a failed feature.
- If a test or check fails and is corrected, briefly note the meaningful
  failure and fix when that context is useful.

## Feature-Specific Coverage

This standard defines how validation is reported; it does not define every
behavior that every feature must test. Task requirements and implementation
plans must still identify the important behavior for their slice. For example:

- authentication work may require enumeration resistance, token lifecycle,
  and session-revocation coverage;
- infrastructure work may require routing, redirect, proxy, and runtime
  assertions;
- UI work may require viewport, device, browser, accessibility, and interaction
  acceptance; and
- commerce-domain work may require ownership, state-transition, totals, and
  transactional-behavior coverage.

The Validation Summary should surface the most important results without
becoming a raw test catalog.

## Reusable Pull Request Template

Use only the sections and checks relevant to the change, and replace all sample
values rather than copying stale counts.

```markdown
## Validation Summary

### Backend
- pytest: <count> passed
- covered: <important behavior>
- migrations: <none or status>

### Frontend
- Vitest: <count> passed
- ESLint: passed
- production build: passed
- covered: <important behavior>

### Infrastructure / Build
- production image: passed
- security scan: passed
- routing validation: passed
- git diff --check: passed

### Human / UAT
- local manual acceptance: PASS
- deployed acceptance: BLOCKED pending deployment
```

## Future Evolution

Commerce Architect may later publish a concise validation summary directly in
GitHub Actions through `$GITHUB_STEP_SUMMARY`. That is a future enhancement,
not part of the current CI contract. Do not create standalone report artifacts
or `TEST_REPORT.md` files as a substitute.
