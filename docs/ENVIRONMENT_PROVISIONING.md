# Environment Provisioning

This runbook defines the repeatable structure for a new Railway environment.
Use authorized human accounts and current Railway documentation for UI labels;
never record rendered secret values.

## Prerequisites

The operator needs:

- Railway project administration for the target environment
- GitHub repository administration and Actions-secret access
- GHCR package administration and a read-only package credential
- DNS-provider access for the intended hostname
- Railway CLI installed and authenticated (`railway --version`,
  `railway whoami --json`)

Before editing, run `railway status --json` with an explicitly linked project,
environment, and service. Confirm the names/IDs against the parameter manifest
and confirm no unrelated staged Railway changes exist.

## Environment parameter manifest

Record non-secret values in an approved operator record:

| Parameter | Hosted development value |
|---|---|
| Railway project | `empowerment-forge.com` |
| Railway environment | `development` |
| Services | `Postgres`, `backend`, `frontend` |
| Public frontend domain | `dev-commerce.empowerment-forge.com` |
| GHCR namespace | `ghcr.io/empowerment-forge` |
| Region / replicas | Current: `ams` / one; review before other environments |
| Data policy | No real customer data; no automatic seed data |

Also record project/environment/service IDs, capacity, secret owners, DNS owner,
and the approved bootstrap-data policy. Do not commit IDs into reusable workflow
logic without an explicit environment-parameterization decision.

## Provisioning sequence

1. Create or select the Railway project and named environment. Reconfirm context.
2. Add one Railway PostgreSQL service. Attach its persistent volume at
   `/var/lib/postgresql/data`; do not add a public TCP domain.
3. Create exactly one `backend` and one `frontend` service. Use approved
   bootstrap image sources if Railway requires an initial source before Registry
   Credentials can be entered.
4. Configure separate read-only GHCR Registry Credentials on both application
   services. Verify pulls, then disable image auto-update.
5. Configure the backend to use an immutable GHCR image, `PORT=8000`, pre-deploy
   command `python manage.py migrate --noinput`, health path `/health/`, and a
   300-second health timeout.
6. Map PostgreSQL values by Railway reference, not copied values:

   ```text
   DATABASE_HOST=${{Postgres.PGHOST}}
   DATABASE_PORT=${{Postgres.PGPORT}}
   DATABASE_NAME=${{Postgres.PGDATABASE}}
   DATABASE_USER=${{Postgres.PGUSER}}
   DATABASE_PASSWORD=${{Postgres.PGPASSWORD}}
   ```

7. Configure an environment-unique `DJANGO_SECRET_KEY`,
   `COMMERCE_ENV=production`, `DJANGO_DEBUG=false`, explicit allowed hosts and
   CSRF trusted origins, secure cookies, and the reviewed forwarded-HTTPS and
   redirect settings. Never reuse values across environments.
8. Configure the frontend immutable image, health path `/`, 300-second timeout,
   and private references `BACKEND_HOST=${{backend.RAILWAY_PRIVATE_DOMAIN}}` and
   `BACKEND_PORT=${{backend.PORT}}`.
9. Attach the frontend public domain and create the required DNS record. Verify
   certificate issuance and HTTPS before enabling HSTS. Keep Cloudflare proxy
   mode and certificate ownership explicitly recorded; they are not yet a
   repository-wide standard.
10. Create a Railway Project Token scoped to this project/environment and store
    it as repository Actions secret `RAILWAY_TOKEN`. Confirm feature branches
    and pull-request jobs cannot access it. GHCR publishing uses the scoped
    workflow `GITHUB_TOKEN`; do not store a second write credential.
11. Trigger the approved first deployment and complete the acceptance checklist.

## First superuser

After a healthy first deployment, explicitly select the project, environment,
and backend service, then open Railway SSH and run:

```bash
python manage.py createsuperuser
```

Enter credentials only at the interactive prompt. Verify that the intended
account alone has active, staff, and superuser flags, then close the session.
Never store the password in documentation, variables, CI, fixtures, seeds, or
shell history.

## Acceptance checklist

- [ ] All three Railway services report healthy/successful deployments.
- [ ] PostgreSQL has a persistent volume and no public TCP domain.
- [ ] Frontend and backend image sources match approved GHCR digests.
- [ ] Image auto-update is disabled on both application services.
- [ ] Backend migration pre-deploy and `/health/` gate are configured.
- [ ] `/` and a client-side SPA fallback path return the frontend.
- [ ] `/api/products/` returns 200.
- [ ] Unauthenticated `/api/auth/me/` returns 401.
- [ ] `/api/` returns the expected 404 (no API index).
- [ ] `/admin/` redirects to login and a representative `/static/` asset loads.
- [ ] `/health/` returns 200 with database status `ok` through approved access.
- [ ] The first superuser was created interactively and no credential was saved.
- [ ] No real customer data, production credentials, or implicit demo seed exists.

Provisioning is not complete until a second authorized engineer can reproduce
these checks using only this repository and approved access.
