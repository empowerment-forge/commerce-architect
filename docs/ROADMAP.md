# Commerce Architect Roadmap

## Current ✅

```text
Browser
  │
  ├── Product / Catalog ✅
  │     product listing ↔ products API ↔ PostgreSQL
  │
  └── Authentication / Account ✅
        │
        ├── USER EXPERIENCE
        │     Registration / verification  register • verify • resend
        │     Session                      login • logout
        │     Account                      profile • change/reverify email
        │     Recovery                     forgot password • reset password
        │
        └── SUPPORTING PLATFORM
              /me identity API
              silent access-token refresh/retry
              refresh rotation/blacklisting
              account-wide session revocation
              verified-email enforcement
```

- The catalog is an end-to-end browser-to-database vertical slice.
- Authentication/account journeys, responsive UI, real-email delivery, and
  deployed acceptance are complete.
- Production-style container images, same-origin routing, HTTPS support, health
  checks, migrations, image scanning, and CI validation are in place.

## Now

1. Verify reproducible clean-environment provisioning.
2. Improve logging, health visibility, monitoring, and alerting.
3. Establish repeatable OWASP-oriented application security testing.

Business-domain modeling and use-case exploration can continue alongside this
operational hardening.

## Operations Path

```text
Provisioning → Observability → Security → Rollback → Backup / restore
```

Rollback and tested recovery remain required before revenue or customer data
depends on the platform.

## Next: Commerce

- Orders
- Checkout
- Payments
- Guest checkout
- Customer/order association
- Additional catalog capabilities as needed

The guest-to-account journey belongs with checkout and orders design. See
[issue #9](https://github.com/empowerment-forge/commerce-architect/issues/9).

## Later Platform Work

- Broader account/password policy hardening
- MFA and stronger account-security capabilities
- Production adoption, rollback, and tested database recovery
- Developer command shortcuts where they add value

## Details

- [Architecture](ARCHITECTURE.md)
- [Build and deployment](BUILD_DEPLOY.md)
- [Developer onboarding](DEVELOPER_ONBOARDING.md)
- [Authentication architecture](USERAUTH_ARCHITECTURE.md)
- [Testing strategy](TESTING_STRATEGY.md)
- [Validation standards](VALIDATION_STANDARDS.md)
- [Password-recovery UAT](uat-testing/UAT_PASSWORD_RECOVERY.md)

GitHub issues hold detailed scope and acceptance criteria. Update this roadmap
only when a major capability or priority changes.
