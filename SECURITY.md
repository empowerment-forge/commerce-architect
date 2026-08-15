# Security Policy

## Reporting a Vulnerability

Do not report suspected security vulnerabilities through public GitHub issues,
pull requests, discussions, or other public channels.

Use GitHub's private vulnerability-reporting option on the Commerce Architect
repository when it is available. If that option is not available, contact the
maintainers through the official
[Empowerment Forge GitHub organization](https://github.com/empowerment-forge)
and request a private reporting channel without including vulnerability details
in a public message. The project does not currently publish a dedicated
security email address.

Include the affected component and version or commit, reproduction steps,
impact, and any suggested mitigation in the private report. Maintainers will
acknowledge the report when practical, investigate it, and coordinate disclosure
and remediation based on severity and project capacity.

If a credential may have been exposed, revoke or rotate it through the owning
service before sharing sanitized evidence. Provider-neutral secret and
operational boundaries are documented in
[`docs/BUILD_DEPLOY.md`](docs/BUILD_DEPLOY.md#operational-requirements).

## Supported Versions

Commerce Architect is early-stage and does not yet publish a formal support
matrix or long-term-support releases. Security fixes are generally applied to
the current actively developed code. Older commits, forks, and deployments may
need to update to receive fixes. Supported-version expectations will become
more explicit when versioned releases begin.
