# Organization Bootstrap and Capability Onboarding

**Status:** Working draft, 2026-09-10. Target design only. Not implementation authority.

## Purpose

Define the minimum platform flow that allows a platform superuser to establish a new Organization, assign its first business owner, and hand control to that owner with zero business capabilities initially enabled.

This document focuses on the first usable operator journey. It does not define the full Operator Experience UI or reopen the broader authorization decisions in `OPERATOR_EXPERIENCE_AUTHORIZATION.md` and `DECISIONS.md`.

## Core principle

Django Admin administers the platform. Commerce Architect operates the business.

The platform superuser bootstraps the Organization and establishes legitimate initial ownership. After that bootstrap, ordinary business operation belongs to Organization-scoped operators using the Commerce Architect operator experience rather than Django Admin.

The Django superuser is therefore not automatically an Organization owner and does not become a normal merchant operator merely because platform authority exists.

## Minimum bootstrap objects

A usable Organization operator path requires, at minimum:

- an active `User` identity with verified email;
- an active `Organization`;
- an `OrganizationMembership` joining the User to that Organization;
- the fixed `OWNER` role on that membership;
- active membership status;
- Organization-scoped authorization capable of evaluating named permissions;
- persisted capability activation state for the Organization.

## Initial site state

A newly bootstrapped Organization should begin with zero business capabilities enabled unless an explicit installation policy says otherwise.

Example:

```text
Organization: Cook and Can
status: active

Capabilities:
Product Commerce: disabled
Service Commerce: disabled
```

Zero enabled capabilities must not prevent an authorized owner from entering the operator application. Capability state governs business functionality, not the existence of the Organization or the owner's authority to manage it.

Therefore this state is valid:

```text
Organization active
+ Owner membership active
+ Product Commerce disabled
= owner can log in and manage Organization-level configuration
```

The owner must still be able to reach Organization, Capabilities, and Team functions allowed by their permissions even when Product Commerce is disabled.

## Bootstrap flow

The intended first-site sequence is:

1. A platform superuser signs in to Django Admin.
2. The superuser creates the Organization.
3. The Organization starts active with zero business capabilities enabled.
4. The superuser establishes the first Owner relationship using an explicit bootstrap or ownership-invitation flow.
5. The intended owner controls a normal Commerce Architect User account and verifies the current email address.
6. Ownership acceptance creates or activates the OrganizationMembership with role `OWNER`.
7. The owner signs in through the normal Commerce Architect login flow.
8. Login resolves the owner's active OrganizationMembership.
9. With one eligible Organization, the owner can be routed directly into that Organization context; with multiple eligible Organizations, context is selected explicitly.
10. The owner can view Organization, Capabilities, Products, and Team areas subject to named permissions and capability state.

The platform superuser may bootstrap ownership, but ordinary operator access must not depend on continued superuser intervention.

## Minimum operator destination

For an owner with one active Organization membership, a conceptual destination is:

```text
/operator/organizations/<organization-id>/
```

The initial operator shell should remain small:

- Organization
- Products
- Capabilities
- Team

Personal account management remains separate from Organization operation.

## Capability and storefront state

Capability activation and public presentation are separate concerns.

For Product Commerce, the minimum state progression is:

```text
Product Commerce disabled
→ business capability unavailable for ordinary catalog mutation or public commerce

Product Commerce enabled + presentation hidden
→ authorized operators can prepare the catalog without publishing it

Product Commerce enabled + presentation shown
→ public storefront is eligible to expose Product Commerce
```

Enabling Product Commerce must not automatically publish the storefront. Disabling Product Commerce should clear public presentation so later re-enablement remains hidden until deliberate publication.

Product records, media, history, and accepted commercial obligations survive capability disable according to their own domain rules.

## Root versus Organization Owner

`root` is an installation/platform authority account in the current environments. That account may administer platform bootstrap through Django Admin, but the target design should not treat `root` as the merchant owner by default.

A merchant owner should operate with a normal User identity plus OrganizationMembership and scoped Owner permissions. This preserves the boundary between platform administration and business operation.

The bootstrap mechanism must therefore establish ownership explicitly rather than infer ownership from `is_superuser`, `is_staff`, email address, or Organization creation alone.

## Minimum implementation slice

The first useful vertical slice does not require the full future Operator Experience.

The minimum foundation is:

```text
OrganizationMembership
→ Owner role
→ Organization-scoped authorization
→ Organization context
→ persisted capability state
→ minimal Capabilities operator screen
```

The proof target is simple:

> A platform superuser can create an Organization and establish its first owner; that owner can sign in, enter the Organization context, see all capabilities initially disabled, and deliberately enable Product Commerce without receiving platform-superuser authority.

This slice should be proven before substantial operator UI polish because later product, media, portability, order, payment, and service-commerce workflows need the same Organization context and authorization boundary.

## Relationship to Catalog Portability

Catalog Portability T12–T17 should not be treated as a hard prerequisite for establishing the operator foundation.

Portability remains important backend/domain work, but future browser exposure of import, export, reset, and related operations depends on knowing:

- which Organization is in scope;
- which authenticated operator is acting;
- which named permission authorizes the operation;
- whether the relevant capability state permits it;
- whether installation-only CLI authority must remain separate.

The operator foundation therefore reduces ambiguity for later portability exposure rather than competing with it.

## Near-term sequencing

A practical near-term sequence is:

```text
focused architecture review / promotion-readiness
→ approve operator target architecture
→ implement minimum Organization operator foundation
→ prove owner login + capability control
→ continue Product Commerce/operator UX
→ complete remaining Catalog Portability integration
→ validate against a real merchant pilot
```

This is sequencing guidance, not implementation authorization. Each implementation slice still requires its own reviewed contract and normal branch/PR/test workflow.

## Open implementation questions

The target direction above is intentionally narrow. A later implementation contract still needs to settle details such as:

- the exact OrganizationMembership schema and constraints;
- how the first ownership invitation/bootstrap token is represented;
- the named permission vocabulary used by the first roles;
- capability persistence schema and transition service;
- recent-authentication requirements for capability and ownership changes;
- the exact operator routes and API boundaries;
- audit requirements for bootstrap and capability changes.

Those details should refine this direction without collapsing platform superuser authority, Organization ownership, capability activation, and public presentation into the same concept.
