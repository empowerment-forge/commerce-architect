# Operator-foundation repository inventory

**Status:** Factual repository inventory, 2026-09-10. Draft/supporting material
only. This document is not architecture authority and does not authorize
implementation.

## Scope and baseline

This inventory was prepared from the current repository, `origin/develop`, the
current operator-design branch, available local/remote branches, migrations,
backend/frontend code, and Markdown documentation. The branch has now been
reconciled with the `origin/develop` T11 baseline and contains only the
operator/catalog draft documents plus this inventory as unique work.

## Currently implemented

| Concept | Evidence and factual boundary |
| --- | --- |
| Account identity | Django `User`, `EmailVerification`, `AccountSecurityState`, and `AccountProfile` exist in [account models](../../../backend/accounts/models.py). JWT authentication, email verification, password recovery, and account identity endpoints exist. This is account identity, not Organization membership. |
| Organization root | [Organization](../../../backend/organizations/models.py) exists with name, active/inactive status, and timestamps. Its foreign-key relationships are used by catalog data. |
| Product Commerce ownership | [Product and ProductImage](../../../backend/catalog/models.py) exist. Product has a protected Organization foreign key; Product/ProductImage have portable identities and catalog constraints. |
| Catalog Organization scoping and locking | [Catalog services](../../../backend/catalog/services.py) require an explicit active Organization for scoped queries and use a five-second PostgreSQL Organization-row lock for supported catalog writes. |
| Product Commerce portability | `origin/develop` contains T09 full export, T10 reconciliation/compatibility planning, and T11 durable operation receipts. Evidence is in `backend/catalog/portability/exporter.py`, `backend/catalog/portability/planner.py`, `backend/catalog/portability/compatibility.py`, `backend/catalog/portability/receipts.py`, and catalog migration `0005_catalog_operation_receipt` on that baseline. |
| Public storefront selection | [Catalog views](../../../backend/catalog/views.py) read the explicitly configured `STOREFRONT_ORGANIZATION_ID` and return active physical Products for that one Organization. Missing or invalid configuration fails closed with a 503. |
| Django Admin boundaries | Organization Admin is restricted to active superusers. Product Admin is scoped to the configured storefront Organization and physical Products; ProductImage Admin is scoped to that Organization, restricts module access to active superusers, and makes the storage key read-only. Account Admin uses Django’s built-in User/model-admin boundary. |
| Authentication authorization primitives | API views use DRF `AllowAny` or `IsAuthenticated` for the existing account flows. Django’s built-in `is_staff`, `is_superuser`, and model permissions remain the available Admin primitives. |

## Existing design/documentation

| Concept | Evidence and factual boundary |
| --- | --- |
| Future delegated operator authorization | [USERAUTH_ARCHITECTURE.md](../../USERAUTH_ARCHITECTURE.md) describes the identity/authentication direction and future delegated authorization work. It does not define or implement OrganizationMembership. |
| Future ownership and customer separation | [PLATFORM_PHILOSOPHY.md](../../PLATFORM_PHILOSOPHY.md) distinguishes Organizations, ownership, and customer data at a principles level. It does not provide Customer or membership schemas. |
| Historical owner-operated architecture | [ARCHITECTURE_v1.2.md](../../ARCHITECTURE_v1.2.md) documents an earlier Phase 1 owner-operated direction, including Django authentication/permissions and ownership alignment. It is historical context, not current runtime authority. |
| Operator application direction | [UX_ARCHITECTURE.md](../../UX_ARCHITECTURE.md) discusses frontend authentication, authorization, and application direction. The current frontend still combines account/authentication panels with product browsing; it does not implement an operator shell or Organization context selector. |
| Current operator draft | [OPERATOR_EXPERIENCE_AUTHORIZATION.md](OPERATOR_EXPERIENCE_AUTHORIZATION.md), [DECISIONS.md](DECISIONS.md), and [NEXT_PROMPT.md](NEXT_PROMPT.md) are working drafts only. They describe OrganizationMembership, roles, capabilities, operator context, customer separation, and future workflows as target design material, not implemented behavior. |

## Historical/obsolete

| Concept | Evidence and factual boundary |
| --- | --- |
| Prior Catalog Portability branch state | The old `feature/catalog-portability-t10-reconciliation` branch is absent locally and remotely; T10 is integrated through PR #88. No historical branch with unique OrganizationMembership or Customer implementation was found among the available local/remote refs. |
| Earlier architecture assumptions | `docs/ARCHITECTURE_v1.2.md` is explicitly earlier architecture context. It must not be read as evidence that its proposed permissions or ownership structures exist in code. |

## Not found in the inspected repository state

The following concepts were not found as implemented models, migrations, or
application services on `origin/develop`:

- `OrganizationMembership` or another persisted Organization-membership table;
- membership roles, fixed role-to-permission mappings, or delegated
  Organization permissions;
- `Customer` or guest-customer models and services;
- persisted capability activation/configuration state;
- a distinct Product Commerce capability switch separate from Organization
  status and storefront configuration;
- storefront presentation/exposure state separate from the single configured
  storefront Organization and Product `is_active` state;
- invitation records, invitation acceptance, or membership lifecycle state;
- owner/ownership membership semantics or last-owner protection;
- an Organization context selector or tenant-aware operator workspace;
- a purpose-built operator UI/shell;
- operator-scoped authorization services beyond the existing authentication,
  Django Admin, and catalog-scope boundaries;
- a general role/permission policy service or custom-role designer.

Email verification and password recovery are present, but they are account
security flows, not invitations or Organization-membership acceptance.

## Branch review

The available local/remote branches are the reconciled operator draft branch,
`develop`, `main`, and dependency-update branches. No other available branch contains meaningful unmerged
OrganizationMembership, Customer, capability, authorization, role, permission,
or operator-application work. The current operator branch is at the same
integrated T09–T11 baseline as `origin/develop`; its unique changes are
documentation under `docs/drafts/` only.

## Evidence boundary

Absence in this inventory means no matching implementation or design artifact
was found in the inspected repository state and available refs. It does not
decide whether the draft target architecture should be approved, promoted, or
implemented.
