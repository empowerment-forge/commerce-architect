# Operator experience decision record

**Status:** Working draft, 2026-09-10. Selected recommendations for review only.
Not authoritative project documentation or implementation authority. The branch
remains unmerged.

This record compares the remaining reasonable choices and explains the selected
policies in [the architecture draft](OPERATOR_EXPERIENCE_AUTHORIZATION.md).
It does not reopen the shared identity, Organization root, Customer/operator
separation, fixed-role, modular-monolith, or immutable-media decisions.

## D01 — Ownership

**Choices:** one transferable owner; multiple equal owners; multiple owners
with a primary owner or quorum rules.

**Select:** multiple equal owners with a last-active-owner guard. Explicit
bootstrap and accepted ownership offers handle grants and transfers; transfer
acceptance changes both memberships atomically. A co-owner can remove another
owner with recent authentication, subject to the guard. This avoids a single
point of routine access loss without a governance engine.

**Invariant:** ordinary actions cannot leave an operational Organization without
an active Owner membership linked to an active User. Security suspension can
block a compromised last owner; it never authorizes an automatic replacement.
Ownerless normal operator access stops pending recovery. Temporary verification
gates do not erase ownership.

**Human input:** dispute/recovery evidence and any requirement for joint consent.
These are business authority questions, not facts derivable from the User table.
See [architecture section 4](OPERATOR_EXPERIENCE_AUTHORIZATION.md#4-organizationmembership-and-roles).

## D02 — Initial role grants

**Choices:** broad speculative grants across future domains; minimal current
grants; a more detailed collection of staff profiles immediately.

**Select:** four fixed roles with explicit current Organization/catalog actions.
Owner governs ownership and administrators; Administrator manages business
settings, capabilities, and Manager/Staff memberships; Manager edits the catalog
and images; Staff reads basic Organization/catalog information. Keep media,
product edits, public exposure, capability controls, and team governance distinct.
No bundles or individual overrides initially.

**Invariant:** no numeric inheritance or wildcard future permissions. Customer,
order, payment, inventory, and scheduling actions remain unassigned until their
domain release. This replaces revision 1's speculative future-domain grants.

**Human input:** actual assistant duties and live-edit approval requirements.
The first matrix is selected; a role that does not fit a real job must be
reviewed rather than granting Manager to get one missing action. See [section 4](OPERATOR_EXPERIENCE_AUTHORIZATION.md#4-organizationmembership-and-roles).

## D03 — Membership lifecycle

**Choices:** create Users/memberships from invited emails; make invitation intent
separate; activate access without recipient acceptance.

**Select:** separate, expiring invitation intent; one retained membership per
User/Organization; active, suspended, or revoked membership status. Acceptance
needs the intended account's verified current email, the single-use invitation
proof, and the inviter's still-valid grant authority. Resume suspended access
explicitly; revoked access requires fresh invitation and acceptance.

**Invariant:** pending intent grants no access, email change cannot move a bound
membership, and acceptance cannot bypass suspension or elevate an existing active
membership. Consultants use the same access lifecycle without employment claims.

**Human input:** none needed to select this lifecycle. Seven-day invitation
expiry is an adjustable operational default. See [section 4](OPERATOR_EXPERIENCE_AUTHORIZATION.md#4-organizationmembership-and-roles).

## D04 — Capability and presentation state

**Choices:** conflate activation/public exposure; preserve a latent shown setting
while disabled; clear shown on disable and require explicit republication.

**Select:** separate settings, with disable atomically clearing presentation.
Re-enable remains hidden. Enabled/hidden permits authorized preparation;
disabled permits configuration, scoped reads, and later authorized export, but
no product/image mutations, import, or reset. This avoids accidental publication.

**Invariant:** showing never activates; activation never publishes; new public
Product Commerce activity needs both gates and domain eligibility. Product flags,
stock, media, and history survive disable. Accepted obligations continue under
their own domains; unaccepted work rechecks gates at commitment.

**Human input:** actual existing-storefront backfill and future Orders acceptance
semantics. The state-transition choice itself is resolved. See [section 6](OPERATOR_EXPERIENCE_AUTHORIZATION.md#6-capability-and-permission-model).

## D05 — Account and Customer cardinality

**Choices:** several directly linked Customers per account/Organization; one
direct linked relationship; require every Customer to have an account.

**Select:** Customer's User link is optional, with at most one direct Customer
link per User/Organization initially. Guest duplicates can remain unlinked.
This gives self-service a clear scope while preserving guest commerce and
historical records.

**Invariant:** registration grants neither Customer history nor operator access.
Guest claims require proof for the specific relationship/transaction and account
control; matching email alone cannot bind or merge. A conflicting second link
goes to reviewed reconciliation, not silent merge or wider access. Original
record identities and transaction snapshots survive corrections.

**Human input:** any actual household/company/delegated-payer requirement before
applying constraints to data. No such need is established here. See [section 3](OPERATOR_EXPERIENCE_AUTHORIZATION.md#3-identity-and-human-roles).

## D06 — Authentication strength

**Choices:** accept any valid JWT for every action; require MFA for all routine
work; make stronger authentication specific to higher-impact actions.

**Select:** active verified identity and current security-generation checks for
all operator requests. Require recent credential authentication for governance,
team, capability, and exposure changes; select a five-minute freshness window.
Require MFA before delegated production self-service for ownership, bulk data
operations, refunds, and platform privilege/recovery actions.

**Invariant:** token refresh is not reauthentication; freshness/MFA never adds
permissions. Missing authentication mechanisms keep affected actions unavailable.
Current verification, refresh revocation, and password-change functions do not
already implement this complete policy.

**Human input:** responsibility and evidence for factor/account recovery.
Factor choice/enrollment and proof transport are later technical design work,
not reasons to invent authentication support now. See [section 5](OPERATOR_EXPERIENCE_AUTHORIZATION.md#5-authorization-evaluation-and-enforcement).

## D07 — Technical support

**Choices:** implied merchant-data access for all technical staff; no support
inspection ever; explicit scoped inspection and exceptional recovery procedures.

**Select:** minimal technical diagnostics, plus separately authorized,
Organization-specific, reasoned merchant-data inspection when needed. Default
inspection to read-only and time-bounded. Exceptional ownership/security recovery
is superuser-only initially. No impersonation or universal operator bypass.

**Invariant:** technical status grants no implicit customer, catalog bulk, or
financial access. Preserve real actor, scope, reason, outcome, and audit;
business mutation and successful audit commit together. Installation credentials
remain a separate trust boundary.

**Human input:** support authorization policy, recovery adjudication, and audit
retention/readership. A generic `change_user` grant cannot substitute for these
boundaries. See [section 5](OPERATOR_EXPERIENCE_AUTHORIZATION.md#5-authorization-evaluation-and-enforcement) and [section 7](OPERATOR_EXPERIENCE_AUTHORIZATION.md#7-django-admin-boundary).

## D08 — First image workflow

**Choices:** restore Admin/raw-key creation; build a media library/direct-storage
platform; add a narrow product-scoped workflow using existing verified storage.

**Select:** one file per upload request, alt text, append/reorder, primary choice,
and association removal within Products. First-image primary is a convenience;
zero primary remains valid. Defer one-click replacement, transformations, private
drafts, shared asset browsing, garbage collection, and bulk media tooling.

**Invariant:** verified bytes precede association commit; final scoped authority
is rechecked. Operation UUID plus semantic fingerprint and durable receipt prevent
duplicate mutation after retries. Collection preconditions reject stale edits.
Removal never deletes immutable bytes, and a receipt replay never resurrects an
image. Public media is public by URL even while presentation is hidden.

**Human input:** whether public prelaunch assets meet the actual business need.
The minimum workflow and retry direction are settled; transport details require
the later implementation contract. See [section 10](OPERATOR_EXPERIENCE_AUTHORIZATION.md#10-productimage-supported-human-workflow-direction).

## D09 — First operator experience

**Choices:** a full business console immediately; continue merchant use of Admin;
a small shell with real Organization and product-media operations.

**Select:** the small shell in the existing SPA: Organization, Products,
Capabilities, and Team, filtered by permissions. Personal account is separate.
Honor an authorized intended route, then a valid prior context, then the sole
operator Organization or an explicit chooser. Preserve intentional shopping.
Retain the configured single public storefront initially.

**Invariant:** every request carries explicit Organization context and is checked
server-side. Switching context cannot retarget an already dispatched mutation or
silently leak another Organization's cached data. No unused future-domain menus.

**Human input:** job-fit acceptance before staff rollout; no unresolved need for
a second frontend or service. See [navigation](OPERATOR_EXPERIENCE_AUTHORIZATION.md#8-operator-application-ownership-and-navigation), [routing](OPERATOR_EXPERIENCE_AUTHORIZATION.md#9-login-destination-and-context-selection), and [implementation sequencing](OPERATOR_EXPERIENCE_AUTHORIZATION.md#12-near-term-implementation-implications-after-a-separate-implementation-request).

## D10 — Portability exposure

**Choices:** make all CLI authority available through ordinary catalog edits;
keep CLI only forever; add a later permissioned browser adapter over the domain
services.

**Select:** the later adapter. Explicit future grants: Owner/Administrator export
and merge import; Owner-only replace and soft reset. Preview requires the
intended apply permission. Manager/Staff receive none. Destructive purge and
snapshot-stock restoration remain guarded installation-operator development
operations with no Organization self-service grant.

**Invariant:** a command caller's claimed User ID is not authentication. Browser
authorization does not weaken preview freshness, package validation, locking,
receipts, or production history/stock protections. Disabled capability allows
authorized export, not import/reset. No T12 or later work is implemented here.

**Human input:** no additional product decision needed for this direction;
shipping depends on the underlying services and separately reviewed release
scope. See [section 11](OPERATOR_EXPERIENCE_AUTHORIZATION.md#11-future-catalog-portability-exposure).

## D11 — Storefront composition seam

**Choices:** let every capability own its public placement permanently; create a
generic storefront-section/page-builder model now; use capability-owned sections
initially and add storefront-level composition when more than one real section
requires ordering.

**Select:** the third, hybrid direction. Product Commerce owns its initial
hidden/shown presentation and supplies the first public Products section. The
public application consumes a storefront-description boundary rather than
mounting Products as its root. Do not persist a generic section record for the
first release. When a second concrete public section arrives, the storefront
owns cross-capability section instances/order while each capability owns its
content, eligibility, validation, and public representation.

**Invariant:** Product Commerce is one possible storefront contribution, not the
storefront itself. Hidden presentation omits the entire Product section and its
data request while retaining the shared brand/authentication shell. Capability
activation, presentation, resource state, permission, and future section order
remain separate. No capability independently assigns global order relative to
unknown capabilities.

**Human input:** select the first real non-product content use case and who may
manage future cross-capability ordering before creating its schema. Organization
welcome copy and existing-storefront backfill are also product/deployment choices;
the safe defaults are no invented placeholder content and explicit migration
policy. See the [storefront refinement](STOREFRONT_CAPABILITIES_AND_FIRST_OPERATOR_EXPERIENCE.md).

## Review outcome

The eleven areas now have selected recommendations. Remaining human inputs,
repository conflicts/gaps, prerequisites, and promotion conditions are recorded
in architecture sections 13–14. The draft is ready for focused review, **not
promotion or implementation**. The operator architecture, decision record, and
storefront refinement do not belong in the authoritative documentation map yet.
