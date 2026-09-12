# Astra handoff

**Status:** Factual supporting handoff, 2026-09-10. Not architecture authority
and not implementation authority.

## Baseline and branch

- Branch: `codex/operator-experience-authorization-design`
- Reconciled baseline commit: `b1fe9ad6c0cd3de1bb05787449bb8d3f33c57a85`.
- Current handoff commit: `0db8b94`.
- `origin/develop`: T11 merge `c79301a`
- The branch was reconciled by merging `origin/develop`; no draft content was
  rewritten and no merge into `develop` occurred.
- Unique branch work remains documentation only under `docs/drafts/`.

## Implemented operator-related foundations

The repository currently implements Django User identity, email verification,
session-generation security state, password recovery, Organization name/status,
Organization-owned Product/ProductImage rows, explicit catalog Organization
scoping and locking, a configured single storefront Organization, and distinct
Django Admin boundaries for Organization, Product, ProductImage, and accounts.
Catalog Portability T09 full export, T10 reconciliation/compatibility, and T11
durable receipts are integrated.

## Confirmed absent foundations

No OrganizationMembership, Customer or guest-customer model, persisted
capability activation state, Product Commerce capability switch, separate
storefront presentation state, membership roles, delegated permission policy,
invitation lifecycle, owner-membership semantics, operator shell, Organization
context switching, or operator authorization service was found.

## Existing design material

The operator proposal and decisions remain under
`docs/drafts/operator-experience/`. Existing identity, platform philosophy,
historical architecture, UX, and catalog documents provide context but do not
implement delegated operator authorization. The preserved Catalog Portability
materials are:

- `docs/drafts/catalog-portability/catalog-portability-v1.md`
- `docs/drafts/catalog-portability/t08-media-implementation-contract.md`
- `docs/CATALOG_PORTABILITY.md` as the separate current committed contract

## Important baseline differences

The operator draft describes membership-based roles, capability state,
presentation state, invitations, customer separation, and an operator
workspace. The current code has only Organization status, Product visibility,
single-storefront configuration, Django/Admin permissions, and account
authentication. Those are factual gaps, not decisions resolved by this handoff.

The Catalog Portability full draft was written against earlier commits and its
T01–T08 narrative is not a status report. T09–T11 are implemented on the
current baseline; T12–T17 remain planned and were not started.

## Stale/transient references

The preserved drafts still reference `/tmp/catalog-portability-design/` and
`/home/forge/dev/repos/commerce-architect/` in source/baseline links, and they
contain historical baseline commits such as `e322b55` and `68227f4`. These are
useful provenance markers but are not portable repository links or proof of
current state. No substantive rewrite was made.

## Architectural judgment still required

A later review must decide, rather than infer from repository facts:

1. OrganizationMembership fields, role model, permission vocabulary, and
   ownership/last-owner rules.
2. Customer versus guest-customer boundaries and their relationship to account
   identity.
3. Capability activation, Organization activation, storefront presentation,
   and Product visibility semantics.
4. Operator context selection and purpose-built UI boundaries versus Django
   Admin responsibilities.
5. Invitation and recent-authentication/security requirements.
6. Promotion and permanent disposition of the operator and Catalog Portability
   draft material.
7. The required focused architecture review before T12 atomic import work.
