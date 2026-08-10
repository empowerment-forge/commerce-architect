# Commerce Architect Public Repository Roadmap

## Purpose and Status

This document is the canonical checklist for preparing Commerce Architect to
become a public open-source project stewarded by Empowerment Forge. It covers
safe publication, licensing, stewardship, repository ownership, community entry
points, security readiness, and repository governance. It does not replace the
product roadmap.

Current official repository:

<https://github.com/empowerment-forge/commerce-architect>

**COMPLETE:** Repository ownership transfer to Empowerment Forge.

**IN PROGRESS:** Public-readiness work. The repository remains private.

**COMPLETE:** The component-specific software licenses are selected and their
license artifacts are present.

**DECISION REQUIRED:** Final CLA and contributor-rights terms have not been
selected.

Publication is more than making source files visible. Commerce Architect should
become a genuine open-source commerce application platform that developers,
consultants, agencies, businesses, and organizations can inspect, use, modify,
fork, deploy, and extend. Adopters should control their implementation without
depending on Empowerment Forge to operate it or accepting unnecessary vendor
lock-in.

At the same time, Empowerment Forge should preserve the long-term identity and
stewardship of the official Commerce Architect project. Licensing and governance
must not accidentally surrender control of the official repository, release
process, project identity, or branding, nor prevent legitimate future
Empowerment Forge services and commercial offerings.

## Priority Labels

- **BLOCKER BEFORE PUBLIC:** Publication must not proceed until resolved.
- **SHOULD COMPLETE BEFORE PUBLIC:** Strong public-readiness expectation; any
  exception requires an explicit, documented acceptance.
- **CAN FOLLOW AFTER PUBLIC:** Useful hardening or community maturation that does
  not automatically block publication.
- **DECISION REQUIRED:** An unresolved choice that must be made deliberately.

## Open-Source Freedom and Official Project Stewardship

Open-source freedom and official project stewardship are related but distinct.

### Open-Source Freedom

The selected model should preserve these principles:

1. Commerce Architect remains genuinely open source.
2. Anyone may use Commerce Architect to operate their own business.
3. Developers, consultants, and agencies may build businesses around Commerce
   Architect.
4. Users may inspect, modify, deploy, and control their own implementation.
5. Forking remains possible.
6. Commercial use is encouraged.
7. The treatment of private modifications to community work is considered
   deliberately and, where the selected model allows, community contribution is
   encouraged.
8. The project should avoid casually adopting a model that allows a large SaaS
   or cloud provider to fork Commerce Architect, improve it privately, sell the
   hosted derivative, and contribute nothing back.
9. No future commercial strategy should require taking Commerce Architect away
   from the open-source community.

### Official Project Stewardship

Open licensing does not grant control over the official project. Empowerment
Forge should remain the founding steward of:

- The official Commerce Architect repository
- The official release process and release artifacts
- The Commerce Architect project identity
- Official trademarks, names, logos, and branding
- Maintainer appointment and repository governance
- The direction of the official project

The licensing and contributor model should preserve legitimate future
Empowerment Forge implementation, hosting, support, training, integration, and
other commercial offerings without restricting adopters' open-source freedoms.

**DECISION REQUIRED:** Define the boundary among copyright licensing,
contributor rights, official-project governance, and trademark/branding policy.

## Current Application Boundaries

**COMPLETE:** The application now has explicit sibling component boundaries:

```text
backend/   Django / DRF / Python commerce platform
frontend/  React / Vite / TypeScript client
```

The backend extraction preserved runtime behavior, APIs, Compose topology, CI
behavior, PostgreSQL data, backend and frontend tests, and frontend behavior.
This boundary clarifies ownership and supports a different license for each
component.

## Licensing and Stewardship Study

**IN PROGRESS:** Component licenses and license artifacts are established.
Dependency and asset compatibility review and contributor terms remain open.

### Selected Component Model

**COMPLETE:** Commerce Architect uses a component-specific licensing model.

- `backend/`: `AGPL-3.0-only`. The goal is to preserve genuine
  open-source and commercial-use freedom while discouraging a large SaaS or
  cloud provider from privately modifying the shared backend platform and
  monetizing those covered modifications without making them available to
  network users.
- Backend contributions: a Contributor License Agreement (CLA) is under
  consideration so Empowerment Forge can preserve sufficient rights for
  long-term stewardship and possible future commercial or dual-licensing
  options. No CLA exists, its terms have not been selected, legal review may be
  appropriate, and contributor copyright and relicensing terms remain a
  decision required.
- `frontend/`: `Apache-2.0`, giving merchants, agencies, and developers broad
  freedom to adopt, commercially use, and customize the client, including in
  proprietary applications subject to the license terms.

Business Source License 1.1 was not selected. It is source-available rather than
an OSI open-source license and would represent a different philosophical choice.

### Candidate Licenses

- [x] Evaluate Apache License 2.0.
- [ ] Evaluate GPLv3.
- [x] Evaluate AGPLv3.
- [ ] Evaluate MPL 2.0.
- [ ] Use MIT as a permissive baseline for comparison.
- [ ] Use BSD 3-Clause as a permissive baseline for comparison.

### Evaluation Dimensions

For each candidate, document:

- [ ] Commercial-use rights
- [ ] Inspection and modification rights
- [ ] Redistribution obligations
- [ ] SaaS and network-use behavior
- [ ] Copyleft scope and triggering events
- [ ] Patent grants, retaliation, and patent-risk implications
- [ ] Fit for agency and consulting use
- [ ] Enterprise adoption friction
- [ ] Ability for adopters to own and control their implementation
- [ ] Ability for third parties to create proprietary derivatives
- [ ] Treatment of privately hosted modifications
- [ ] Implications for future dual licensing or commercial offerings
- [ ] Contributor rights and inbound/outbound license consistency
- [ ] Compatibility with current and likely future dependencies
- [ ] Notice, source-distribution, and operational compliance burdens

### Historical Case Studies

Study both successful and painful long-term outcomes before selecting a model:

- [ ] PostgreSQL
- [ ] SQLite
- [ ] Elasticsearch and OpenSearch
- [ ] Redis
- [ ] MongoDB
- [ ] Terraform and OpenTofu
- [ ] MySQL and MariaDB
- [ ] Linux
- [ ] ownCloud and Nextcloud

For each case, note the original goals, license/governance changes, community and
vendor response, fork dynamics, commercial incentives, trademark effects, and
lessons applicable to Commerce Architect.

### Licensing and Stewardship Decisions

- [x] Select `AGPL-3.0-only` for `backend/`.
- [x] Select `Apache-2.0` for `frontend/`.
- [x] Select a component-specific licensing model.
- [x] Establish a temporary contribution policy that welcomes non-code
  participation while external code pull requests are paused.
- [ ] **DECISION REQUIRED:** Select any CLA or other contributor model and its
  copyright and relicensing terms.
- [ ] Obtain appropriate legal review before adopting a CLA.
- [ ] **DECISION REQUIRED:** Select contributor relicensing and sublicensing
  language, if any.
- [x] Decide how SaaS/network-use modifications should be treated by selecting
  `AGPL-3.0-only` for the backend.
- [ ] **DECISION REQUIRED:** Select the initial contributor licensing model,
  such as inbound=outbound, a Developer Certificate of Origin, or a contributor
  agreement if one is justified.
- [ ] **DECISION REQUIRED:** Decide copyright ownership and stewardship.
- [ ] **DECISION REQUIRED:** Decide the initial trademark and branding posture.
- [ ] **DECISION REQUIRED:** Determine whether future dual licensing must remain
  possible and what contributor permissions it would require.
- [ ] Decide future SDK licensing.
- [ ] Decide future CLI licensing.
- [ ] Define extension and plugin licensing expectations.
- [ ] Decide whether documentation needs a separate license.
- [x] Add a clear top-level explanation of multi-license boundaries in
  `LICENSE.md`.
- [ ] Add SPDX identifiers or other license metadata where useful.
- [x] Add `backend/LICENSE`, `frontend/LICENSE`, and `LICENSE.md`.
- [ ] Verify dependency and asset license compatibility.
- [x] Record the component license decisions and rationale.

## Repository Ownership and Organization Transfer

The repository was transferred with GitHub's repository-transfer capability
rather than recreated. The transfer preserved Git history and GitHub project
metadata.

### Before Transfer

- [x] Confirm the current maintainer had the repository admin access required to
  transfer `anthonylpeterson/commerce-architect`.
- [x] Confirm the `empowerment-forge` organization could receive the repository.
- [x] Confirm the target repository name was available.
- [ ] Confirm no conflicting fork network prevents transfer.
- [x] Review Empowerment Forge owners, teams, roles, and repository-creation
  permissions.
- [ ] Decide who receives admin, maintain, write, triage, and read access.
- [x] Verify GitHub App and Codex authorization followed the transfer.
- [x] Verify Actions and workflow permissions remain appropriate.
- [ ] Record existing branch settings and rulesets for post-transfer review.
- [x] Identify and update the local Git remote.
- [ ] Identify documentation, badges, webhooks, deployment integrations, and
  connector references tied to the old owner.

### Transfer

- [x] Transfer the repository to `empowerment-forge` through GitHub.
- [x] Preserve the repository rather than recreating or reinitializing it.

### After Transfer

- [x] Confirm the owner is `empowerment-forge`.
- [x] Confirm full Git history is intact.
- [x] Confirm issues are intact.
- [x] Confirm pull requests and review history are intact.
- [ ] Confirm tags and releases are intact.
- [x] Confirm Actions still run.
- [x] Confirm `develop` is synchronized with `origin/develop`.
- [ ] Reconcile and verify `main` for publication.
- [x] Update the local Git remote to
  `git@github.com:empowerment-forge/commerce-architect.git`.
- [x] Confirm local Git/SSH fetch and push access.
- [x] Confirm Codex and `gh` authentication can access the private repository.
- [x] Confirm the ChatGPT GitHub connector can access the private repository.
- [x] Review organization ownership and repository administrator access.
- [ ] Review branch settings and rulesets after transfer.
- [ ] Find and update links that incorrectly use the previous repository owner.

**COMPLETE:** The transfer has occurred successfully. Git history, issues,
pull-request history, Actions, access, and the private repository state were
preserved.

## Initial Governance and Contributor Access

The initial governance model should remain simple and explicit.

Making a repository public permits anyone to read and fork it. It permits people
to propose changes through pull requests. It does **not** give arbitrary users
permission to push commits to the official repository.

The normal external contribution path should be:

```text
fork
  ↓
branch
  ↓
pull request
  ↓
review
  ↓
CI
  ↓
maintainer merge
```

Access levels remain distinct:

- **Public read/fork:** available to everyone after publication.
- **Pull-request contribution:** available without repository write access.
- **Write:** intentionally granted to trusted contributors who need to push
  branches to the official repository.
- **Maintain:** granted to trusted maintainers responsible for project and
  repository operations.
- **Admin:** narrowly granted to people responsible for sensitive settings,
  security, access control, and ownership operations.
- **Organization ownership:** controlled by Empowerment Forge organization
  owners and separate from ordinary repository contribution.

Initial governance checklist:

- [ ] Record Empowerment Forge as founding steward of the official project.
- [ ] Define initial maintainer responsibilities and decision authority.
- [ ] Grant write, maintain, and admin permissions explicitly.
- [ ] Protect `main` and `develop` from casual direct modification.
- [ ] Document the expected fork/branch/PR/review/CI workflow.
- [ ] Document how trusted contributors may become maintainers.
- [ ] Defer formal councils, elections, or complex governance until an actual
  maintainer community makes them useful.

## Completed Audit Baseline

The initial public-readiness audit established this baseline. Findings should be
revalidated before publication.

### Secrets and History

- No literal Gemini API key was found in current HEAD or reachable Git history.
- Historical Gemini code read `GEMINI_API_KEY` from the environment only.
- No high-confidence provider secret was found.
- No Git-history rewrite is currently warranted.
- A dedicated final secret scanner is still required before publication.

### Development Configuration

- Django contains a committed development `SECRET_KEY`.
- Compose contains fixed development PostgreSQL credentials.
- These are development defaults but must not be usable accidentally in
  production.
- No `.env.example` exists.
- `.gitignore` needs broader environment, cache, coverage, IDE, and OS patterns.

### Dependency Security

At the time of the audit, `npm audit` reported:

- 1 critical
- 10 high
- 2 moderate
- 2 low

Directly implicated tooling included Vitest, Vite, and PostCSS. Remediation must
be performed through a dedicated, reviewed dependency change rather than by
automatic audit fixes.

`backend/requirements.txt` is not fully deterministic. A Python vulnerability
scanner was unavailable during the audit, so Python locking/constraints and
automated vulnerability auditing remain planned work.

### Django Deployment Posture

`backend/manage.py check --deploy` reported development-oriented warnings for:

- The development `SECRET_KEY`
- `DEBUG=True`
- Empty `ALLOWED_HOSTS`
- Missing HSTS configuration
- Missing HTTPS redirect configuration
- A session cookie not marked secure
- A CSRF cookie not marked secure

These settings are acceptable only for local development and must not be
mistaken for production configuration.

### Public Documentation and Community Files

- README needs a prominent maturity/status statement.
- Documentation contains conflicting production-readiness language.
- Public readers need a clearer distinction among current implementation,
  frozen architecture, and aspirational design.
- `LICENSE`, `SECURITY.md`, and `CONTRIBUTING.md` are absent and are
  pre-publication priorities.
- `CODE_OF_CONDUCT.md`, issue templates, and a pull-request template are absent
  and may be completed before or soon after publication as appropriate.

## Publication Phases

### Phase 1 — Licensing and Stewardship

**IN PROGRESS:** Component licensing is established. Compatibility review and
contributor/legal decisions remain open.

- [x] Define and approve the initial component-specific licensing principles.
- [ ] Complete the historical case studies.
- [ ] Compare Apache-2.0, GPLv3, AGPLv3, and MPL-2.0.
- [ ] Compare MIT and BSD 3-Clause as permissive baselines.
- [x] Select `AGPL-3.0-only` for `backend/`.
- [x] Select `Apache-2.0` for `frontend/`.
- [x] Decide the approach to SaaS/network-use modifications.
- [ ] Decide the initial CLA or other contributor licensing model.
- [ ] Decide copyright ownership and stewardship.
- [ ] Decide the initial trademark and branding posture.
- [ ] Decide future SDK, CLI, extension/plugin, and documentation licensing.
- [x] Document the multi-license boundary and future SPDX approach.
- [x] Add the required component license artifacts.
- [ ] Verify dependency and asset license compatibility.

Publication must not proceed before dependency and asset compatibility review
and the remaining contributor/legal decisions are resolved or explicitly
accepted.

### Phase 2 — Repository Ownership

**COMPLETE:** Repository ownership transfer. Remaining checks below stay open
where they have not yet been fully verified.

- [x] Verify Empowerment Forge organization permissions.
- [x] Verify the target repository is owned by `empowerment-forge`.
- [x] Transfer the repository to `empowerment-forge`.
- [x] Verify Git history, issues, pull requests, review history, and Actions.
- [ ] Verify tags and releases.
- [x] Update the local Git remote and verify Git/SSH access.
- [x] Verify Codex and `gh` access.
- [x] Verify ChatGPT GitHub connector access.
- [x] Verify organization ownership and administrator configuration.
- [x] Verify `develop` is synchronized with `origin/develop`.
- [ ] Reconcile and verify `main` for publication.
- [ ] Review branch settings and rulesets after transfer.
- [ ] Update owner-specific documentation and external links.

### Phase 3 — Security and Configuration Hygiene

**BLOCKER BEFORE PUBLIC**

- [ ] Move Django `SECRET_KEY` to environment-backed configuration.
- [ ] Separate safe development defaults from production requirements.
- [ ] Ensure production configuration fails closed.
- [ ] Add `.env.example` or an equivalent safe template.
- [ ] Confirm the example file contains no real credentials.
- [ ] Expand `.gitignore` for environment variants, Python environments,
  caches, coverage, IDE state, and OS metadata.
- [ ] Review PostgreSQL host-port exposure.
- [ ] Confirm no development password can be accidentally reused in production.
- [ ] Re-run Django deployment security checks.
- [ ] Document remaining development-only warnings and production requirements.

### Phase 4 — Dependency Security

**BLOCKER BEFORE PUBLIC for unaccepted critical/high findings**

- [ ] Assess every npm critical and high advisory.
- [ ] Upgrade affected frontend dependencies through reviewed changes.
- [ ] Run frontend tests.
- [ ] Run the frontend build.
- [ ] Run frontend lint.
- [ ] Run backend tests.
- [ ] Run `npm audit` again.
- [ ] Establish Python vulnerability auditing.
- [ ] Decide and implement a Python lock or constraints strategy.
- [ ] Add automated dependency updates where appropriate.
- [ ] Document explicitly accepted residual findings, their scope, and review
  date.

### Phase 5 — Public Open-Source Front Door

**BLOCKER BEFORE PUBLIC:** security, contribution, and accurate maturity entry
points.

- [x] Add the selected component license artifacts and repository license map.
- [ ] Add `SECURITY.md`.
- [ ] Define a private vulnerability-reporting process.
- [ ] State that vulnerabilities must not be filed as public issues.
- [x] Add `CONTRIBUTING.md` with the temporary external-code contribution
  policy.
- [ ] Add the selected CLA/contributor terms if required by the final model.
- [x] Document the intended branch, PR, review, and CI contributor workflow.
- [x] Document current contributor licensing expectations without creating a
  CLA.
- [ ] Add maintainer and contact guidance.
- [ ] Add a prominent README maturity/status statement.
- [ ] Remove defensive or stale public-facing wording.
- [ ] Reconcile production-readiness contradictions.
- [ ] Add a concise documentation map.
- [ ] Clarify current, frozen, superseded, and aspirational documents.
- [ ] Verify branding and logo publication rights.
- [x] Link the license map and contribution guide from README.
- [ ] Link the security policy from README after `SECURITY.md` exists.

### Phase 6 — GitHub Public-Repository Configuration

**SHOULD COMPLETE BEFORE PUBLIC or be ready for immediate enablement**

- [ ] Protect `main`.
- [ ] Protect `develop`.
- [ ] Require pull requests where appropriate.
- [ ] Require CI checks.
- [ ] Block force pushes to protected branches.
- [ ] Block protected-branch deletion.
- [ ] Review direct-push permissions.
- [ ] Enable dependency alerts.
- [ ] Enable or verify automated security fixes.
- [ ] Enable secret scanning.
- [ ] Enable push protection.
- [ ] Enable Private Vulnerability Reporting.
- [ ] Add Dependabot configuration.
- [ ] Improve the repository description.
- [ ] Add repository topics.
- [ ] Review current public-bound issues, PRs, and comments.
- [ ] Confirm the `main`/`develop` strategy is understandable to external
  contributors.

Some GitHub security and ruleset features may be unavailable for the private
repository under the current plan. Prepare their intended configuration before
publication and enable or verify them immediately after visibility changes.

### Phase 7 — Final Publication Check

**BLOCKER BEFORE PUBLIC: explicit go/no-go review**

- [x] Repository is owned by `empowerment-forge`.
- [x] Component license artifacts exist and match the selected software
  licenses.
- [ ] `SECURITY.md` exists.
- [x] `CONTRIBUTING.md` exists with the temporary contribution policy.
- [ ] No known critical/high dependency issue remains without explicit
  acceptance.
- [ ] Development secrets cannot masquerade as production secrets.
- [ ] `.env.example` contains no real credentials.
- [ ] Backend tests pass.
- [ ] Frontend tests pass.
- [ ] Frontend build passes.
- [ ] Frontend lint passes.
- [ ] Reconcile the current approved `develop` state into `main`.
- [ ] Confirm the publication-candidate `main` README describes the current
  platform and contains no stale Gemini or architecture-agent language.
- [ ] Final CI passes on the publication candidate.
- [ ] Django deployment posture is understood and documented.
- [ ] A dedicated secret scan passes.
- [ ] Git history contains no credential requiring removal.
- [ ] Personal/private information review is complete.
- [ ] Maintainer publication of Git author metadata is intentional.
- [ ] Branding and logo rights are confirmed.
- [ ] README clearly states project maturity.
- [ ] Documentation links work.
- [ ] Open issues are suitable for public visibility.
- [ ] Branch strategy is documented.
- [ ] GitHub organization permissions are reviewed.
- [ ] `main` and `develop` protection is configured or ready for immediate
  enablement.
- [ ] A private vulnerability-reporting path is ready.
- [ ] Repository description and topics are ready.
- [ ] Maintainer explicitly approves publication.

Final action:

- [ ] **CHANGE VISIBILITY TO PUBLIC**

Changing visibility is a separate, explicitly approved operation. Completion of
this document alone does not authorize publication.

## Immediate Post-Publication Checklist

Run immediately after visibility changes:

- [ ] Confirm the repository loads publicly while logged out.
- [ ] Confirm `LICENSE` renders correctly.
- [ ] Confirm anonymous clone works.
- [ ] Confirm CI still functions.
- [ ] Confirm issues and PRs are visible as intended.
- [ ] Enable or verify GitHub secret scanning.
- [ ] Enable or verify push protection.
- [ ] Enable or verify Private Vulnerability Reporting.
- [ ] Verify dependency alerts.
- [ ] Verify automated security fixes.
- [ ] Verify branch protections and rulesets.
- [ ] Verify organization permissions.
- [ ] Verify repository topics and description.
- [ ] Verify external links and owner-specific URLs.
- [ ] Verify Codex and `gh` access.
- [ ] Verify ChatGPT GitHub connector access.
- [ ] Re-run the primary clone, build, test, and documentation checks from a
  clean environment.

## Non-Blocking Maturity Work

These items are **CAN FOLLOW AFTER PUBLIC** unless circumstances make one
necessary for safe publication:

- [ ] Add `CODE_OF_CONDUCT.md`.
- [ ] Add issue templates and issue configuration.
- [ ] Add a pull-request template.
- [ ] Add a support guide.
- [ ] Evaluate GitHub Discussions when community demand exists.
- [ ] Add CodeQL or equivalent code scanning.
- [ ] Generate an SBOM.
- [ ] Add build provenance.
- [ ] Add signed releases.
- [ ] Pin GitHub Actions to immutable commit SHAs.
- [ ] Pin container images by digest where appropriate.
- [ ] Add release automation.
- [ ] Add container vulnerability scanning.
- [ ] Define formal governance when an actual maintainer community exists.
- [ ] Publish a formal trademark policy when needed.

These tasks should improve project maturity without creating unnecessary
pre-publication bureaucracy.

## Relationship to Other Roadmaps and Architecture

This roadmap complements:

- [ROADMAP.md](ROADMAP.md), which tracks product implementation direction.
- [PLATFORM_PHILOSOPHY.md](PLATFORM_PHILOSOPHY.md), which defines enduring
  ownership, adoption, extensibility, and engineering principles.
- [ARCHITECTURE_v1.2.md](ARCHITECTURE_v1.2.md), which is the frozen Phase 1
  architecture record.

Do not duplicate the complete product backlog here. GitHub issues remain the
source of detailed implementation tasks and acceptance criteria. Update this
roadmap when a public-readiness decision is made, a phase materially advances,
an audit finding changes, or a publication prerequisite is completed.
