# DevOps & Branching Strategy

## Overview

This project follows a simplified GitFlow model to support:

- Controlled release preparation
- Controlled integration
- Enforced test discipline
- Clean commit history
- Future team scalability

---

# Branch Model

## main
- Publication and release branch
- Receives reviewed changes from develop
- Intended to be protected before public release
- No direct commits allowed

## develop
- Integration branch
- All completed features merge here
- Must pass CI before merge

## feature/*
- Short-lived branches
- Created from develop
- Merged into develop via Pull Request
- Deleted after merge

---

# Development Workflow

## CI and deployment consequences

- Pull requests targeting `develop` validate both production images but do not
  publish or deploy them.
- Pushes to `main` validate both images but do not publish or deploy them.
- Pushes to `develop` validate, scan, publish by commit SHA, resolve immutable
  digests, and deploy both services to the Railway development environment.
- Feature-branch pushes do not receive deployment credentials.

See [BUILD_DEPLOY.md](BUILD_DEPLOY.md) for the canonical trigger matrix and
[OPERATIONS.md](OPERATIONS.md) for post-deployment verification.

## 1. Start a Feature

```bash
git checkout develop
git pull origin develop
git checkout -b feature/<feature-name>
