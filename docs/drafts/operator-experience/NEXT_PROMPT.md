Continue the Commerce Architect Operator Experience and Authorization architecture exercise.

IMPORTANT SCOPE

This is a focused repository reconciliation and promotion-readiness review.

Do NOT perform another broad architecture redesign.
Do NOT reopen decisions already selected in the current draft unless you find a concrete contradiction in the repository or an important implementation incompatibility.

Do NOT implement application code.
Do NOT create migrations.
Do NOT modify Catalog Portability implementation.
Do NOT merge the branch.

Keep all work under:

docs/drafts/operator-experience/

The current working documents are:

docs/drafts/operator-experience/OPERATOR_EXPERIENCE_AUTHORIZATION.md
docs/drafts/operator-experience/DECISIONS.md

These remain drafts until explicitly promoted later.

---

PRIMARY GOAL

Reconcile the current operator-experience draft against the actual repository state, including develop and any relevant local branches/worktrees, and determine whether the design is mature enough to promote into:

docs/design/operator-experience/

The review should answer:

1. What existing OrganizationMembership, Customer, capability, authorization, or related foundation work already exists anywhere in the repository or local branches/worktrees?

2. Does that existing work agree with the selected draft decisions?

3. Are there any real contradictions, incompatible assumptions, duplicated concepts, or migration-direction conflicts?

4. Which issues are:
   - true architecture conflicts
   - implementation gaps
   - branch/baseline drift
   - deferred business-policy decisions
   - harmless naming/detail differences

5. Can the current draft be promoted as approved target design without falsely claiming that the behavior is already implemented?

---

REPOSITORY REVIEW REQUIREMENTS

Inspect the actual current repository state and relevant branches/worktrees.

At minimum review:

- current develop
- the existing operator-experience design branch
- any branch/worktree containing Organization, OrganizationMembership, Customer, capability, authorization, role, permission, or operator-related work
- applicable Markdown documentation
- relevant models, services, APIs, Admin configuration, frontend auth/context code, and migrations where needed to establish facts

Do not assume a concept is absent merely because it was absent at the draft's original baseline.

Use repository evidence to distinguish:

CURRENTLY IMPLEMENTED
APPROVED/EXISTING DESIGN
DRAFT-ONLY TARGET STATE
NOT YET DESIGNED

Do not collapse those categories.

---

DECISIONS TO PRESERVE UNLESS CONFLICT IS FOUND

Treat these as selected draft decisions, not questions to reopen casually:

- one shared account identity
- no global business “user type”
- Organization is the business ownership/scope root
- OrganizationMembership represents operator access
- Customer represents commerce relationship
- Django Admin administers the platform
- Commerce Architect operates the business
- fixed roles initially:
  - Owner
  - Administrator
  - Manager
  - Staff
- explicit named permissions, no numeric hierarchy
- multiple equal owners with last-active-owner protection
- invitation lifecycle separate from membership lifecycle
- active / suspended / revoked membership states
- capability activation and public presentation are separate states
- disabling Product Commerce clears presentation to hidden
- re-enabling does not automatically republish
- retained records survive capability disable
- one optional direct Customer link per User/Organization initially
- no identity or Customer linking based on email equality alone
- verified operator identity
- stronger authentication for sensitive/high-impact actions
- no merchant impersonation or universal platform bypass initially
- first operator shell areas:
  - Organization
  - Products
  - Capabilities
  - Team
- ProductImage human workflow belongs inside product management
- verified immutable media boundary remains unchanged
- future catalog portability browser operations require separate permissions
- trusted installation CLI authority remains distinct from Organization self-service authority

Only reopen one of these if repository evidence shows a real incompatibility.
If that happens, identify the contradiction precisely and recommend the smallest correction.

---

FOCUSED RECONCILIATION AREAS

Pay particular attention to:

1. Organization foundation
   - current Organization model and lifecycle
   - any existing ownership assumptions
   - bootstrap behavior
   - active/inactive semantics

2. OrganizationMembership
   - whether a model or design already exists
   - role representation
   - uniqueness/cardinality
   - lifecycle/status
   - invitation handling
   - ownership semantics
   - permission strategy

3. Customer
   - whether a model/design already exists
   - Organization ownership
   - User linkage
   - guest behavior
   - cardinality/deduplication assumptions
   - conflicts with the selected one-direct-link policy

4. Capability foundation
   - whether capability activation/configuration already exists
   - Organization scoping
   - Product Commerce representation
   - public storefront exposure
   - whether any implementation currently conflates activation and presentation

5. Authorization
   - existing Django permissions/groups
   - custom policy/service code
   - superuser/is_staff behavior
   - Organization scoping
   - backend versus frontend enforcement
   - any existing role assumptions

6. Authentication
   - current verification behavior
   - current token/security-generation behavior
   - what would be needed for stricter operator eligibility
   - whether recent-authentication/MFA concepts conflict with existing auth architecture

7. Operator/frontend
   - current SPA structure
   - existing account/login routing
   - whether an operator shell/context layer already exists anywhere
   - likely seams for introducing Organization context without unnecessary restructuring

8. Django Admin
   - current Organization/Product/ProductImage/User Admin policies
   - inconsistencies that matter to the target design
   - distinguish temporary development bridge from intended long-term surface

9. ProductImage workflow
   - confirm existing media/storage primitives support the selected human workflow direction
   - identify only concrete missing orchestration/policy pieces

10. Catalog Portability relationship
   - inspect current T09-T11 state if present
   - reconcile receipt/idempotency concepts with the proposed operator image workflow
   - do not implement or alter T12+
   - identify any terminology or abstraction we should deliberately reuse versus keep separate

---

PROMOTION READINESS

At the end, classify the draft into one of these outcomes:

A. READY TO PROMOTE
The design is internally consistent, reconciled with repository reality, and can move to docs/design/operator-experience/ as approved target architecture, while clearly stating that implementation may lag.

B. READY WITH MINOR EDITS
Only small wording, terminology, cross-reference, or status corrections are needed before promotion.

C. NOT READY
A real unresolved architecture conflict or release-blocking human-policy issue remains.

Do not choose C merely because functionality is not implemented yet.
Approved target design is allowed to precede implementation.

If A or B:
- identify the exact edits needed before promotion
- identify which deferred human-policy questions may remain explicitly deferred without blocking promotion
- recommend whether both:
  - OPERATOR_EXPERIENCE_AUTHORIZATION.md
  - DECISIONS.md
  should graduate together

Do NOT actually move the files to docs/design/ unless explicitly instructed in a later request.

---

OUTPUT

Update the draft documents only where reconciliation findings genuinely require clarification.

If useful, create:

docs/drafts/operator-experience/RECONCILIATION.md

Keep it concise and evidence-focused.

Final report should include:

- repository branches/worktrees inspected
- relevant existing foundations found
- conflicts found
- non-conflicting implementation gaps
- decisions confirmed
- decisions requiring adjustment, if any
- human-policy items that can remain deferred
- promotion-readiness classification: A, B, or C
- exact recommended next step

Do not implement code.
Do not merge.
Do not promote the draft yet.
