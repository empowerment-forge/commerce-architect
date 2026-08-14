# Operations Runbook

Use explicit Railway project, environment, and service context for every command.
Do not paste variable output or unredacted logs into tickets or documentation.

## Status and deployment identity

1. Run `railway status --json` and confirm the project/environment/service.
2. Use `railway deployment list --json` for each application service.
3. Identify the deployment belonging to the expected Git commit and GHCR digest.
4. Wait for terminal status; `SUCCESS` is required before acceptance testing.
5. Compare each Railway image source with the registry digest resolved by the
   corresponding GitHub Actions job.

## Logs and diagnosis

Inspect the smallest relevant time window. Distinguish:

- GitHub Actions image build/test/scan and GHCR publish logs
- Railway registry-pull and build logs
- backend pre-deploy migration logs
- frontend/backend runtime logs
- NGINX request/proxy logs and database availability

Redact authorization headers, cookies, tokens, credentials, user data, and
rendered variables before sharing. A GHCR push failure belongs to GitHub;
registry pull failure to Registry Credentials; migration failure to the backend
pre-deploy phase; health failure to runtime/database readiness; and public
routing failure to NGINX, Railway domain, or DNS/TLS configuration.

## Railway SSH safety

Reconfirm context immediately before SSH. Prefer read-only commands such as:

```bash
python manage.py check
python manage.py showmigrations
```

Do not run manual migrations concurrently with deployment, edit files inside a
container, print environment variables, or change database state without an
approved procedure and current backup evidence.

## Post-deployment acceptance

From an authorized client, verify:

| Request | Expected result |
|---|---|
| `GET /` | 200 frontend |
| `GET /a-client-route` | 200 SPA fallback |
| `GET /api/products/` | 200 |
| `GET /api/auth/me/` without credentials | 401 |
| `GET /api/` | 404; no API index exists |
| `GET /admin/` | 302 to login |
| representative `/static/admin/...` asset | 200 |
| backend `GET /health/` | 200 and database `ok` |

Also confirm all service statuses, private/no-public PostgreSQL exposure, and
the deployed digest. Do not treat expected 401, 404, or 302 responses as faults.

## Migrations

CI tests migrations against disposable PostgreSQL. Railway automatically runs
`python manage.py migrate --noinput` before backend activation. Inspect the
pre-deploy result and use `showmigrations` read-only when necessary.

On failure, preserve the active healthy deployment, capture sanitized evidence,
and decide between a forward fix and application rollback based on schema
compatibility. Never assume rolling back an image reverses a migration.

## Superuser administration

Create the first account only via the interactive procedure in
[ENVIRONMENT_PROVISIONING.md](ENVIRONMENT_PROVISIONING.md). Password resets and
disabling a compromised administrator must also be interactive, authorized, and
verified. Periodically review active staff/superuser accounts. Do not create
privileged users through seeds or CI.

## Credential inventory and rotation

| Credential | Location | Minimum scope / owner |
|---|---|---|
| Railway Project Token | GitHub `RAILWAY_TOKEN` secret | Exact deployment environment; deployment owner |
| GHCR pull credential | Railway Registry Credentials | `read:packages`; package owner |
| `DJANGO_SECRET_KEY` | Railway backend variable | Unique environment; security owner |
| PostgreSQL password | Railway-managed variables | Private database; database owner |
| DNS credential | DNS provider | Required records only; DNS owner |
| Superuser password | Human password manager | Named administrator only |

For rotation: create the replacement at minimum scope, update its consumer,
verify a pull/deploy/login without printing the value, then revoke the old
credential and record date/owner. Rotate immediately after suspected exposure or
owner departure. Changing `DJANGO_SECRET_KEY` invalidates signed application
state and must be treated as a coordinated incident change. Database-password
rotation requires coordinated Railway reference/application verification.

## Rollback

Automated rollback is not implemented. Before an application rollback:

1. Obtain authorization and identify a prior known-good immutable digest.
2. Determine whether migrations since that digest are backward compatible.
3. Preserve current deployment and sanitized failure evidence.
4. Set the affected Railway service to the approved prior digest.
5. Wait for terminal status and run the full acceptance checklist.
6. Reconcile CI/Railway desired state so the next deploy cannot silently restore
   the failed digest.

If schema compatibility is unknown, prefer a forward fix. Do not claim recovery
until the application and data checks pass.

## Backup and restore

**Unresolved operational requirement:** the current Railway plan's backup/PITR
capability, retention, RPO/RTO, encrypted export location, and restore authority
have not been approved or tested. Before treating hosted data as recoverable,
select a policy and restore a backup into an isolated target; verify schema,
representative data, permissions, and application health. Never test restoration
over the active database.

## Incident and access gaps

Alert ownership, notification channel, response times, service objectives,
capacity, and periodic access review are not yet defined. The temporary backend
public domain, Cloudflare/Railway TLS boundary, CSP, and HSTS also require explicit
decisions. Record these as unresolved controls, not assumed platform behavior.
