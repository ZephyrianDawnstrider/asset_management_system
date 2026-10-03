# Render free preview packaging — 2026-10-03

This note describes a packaging target only. No Render service, new database,
container image, or cloud migration has been created or run. The approved
storage target is the existing private Supabase `assets_portfolio` schema.
Hosting real employee or inventory data remains blocked until its credentials,
isolation, artifact review, and operational gates are complete.

## Current deployment boundary

The [Render Blueprint](../render.yaml) is a manual, image-backed template for
one free web service. Its image URL is intentionally an unusable placeholder
until an immutable image is built, scanned, and published through the approved
route. It cannot
fall back to a Git-based Docker build. Automatic deploys are off. There is no
database, disk, worker, cron job, pre-deploy command, or paid fallback in the
Blueprint. `DATABASE_URL` is a required external PostgreSQL setting with no
default; the authorized operator must supply the connection scoped to the
approved existing Supabase `assets_portfolio` schema after credential and
isolation checks. The application must not start with SQLite as a production
fallback. No Render PostgreSQL resource is selected or declared.

The manual [`render-image.yml`](../.github/workflows/render-image.yml) workflow
builds only on `workflow_dispatch` from `main`. It checks that the source repo
is public before checkout, disables checkout credential persistence, and lets
Docker's deny-by-default context filter the runner checkout before building.
The workflow scans the unstarted image, checks production fail-closed behavior,
and requests an offline `/health/` 503 while the disposable build database has
no migrations. The `publish_image` input defaults to false. It uploads no
source bundle and passes no application/database credentials to the build.
GitHub documents standard hosted runners as free for public repositories; this
does not make the repository contents private. The runner checkout still
materializes the tracked historical database before Docker applies its context
filter, and the repository itself remains publicly cloneable. The filter keeps
the file out of the build context and image; it does not remedy that existing
source exposure. See [GitHub-hosted runner terms](https://docs.github.com/en/actions/reference/runners/github-hosted-runners).

GHCR's first package is private by default. If the reviewed image is published,
the package owner must manually change its visibility to public before Render
can pull it without registry credentials. GitHub documents that making a
package public cannot be undone, so do that only after the sanitized image and
digest are accepted. See [GitHub package visibility](https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility).

The Git checkout contains a tracked historical `db.sqlite3`. A Git-based
Docker build would still clone the repository, so `.dockerignore` cannot
prevent that file from reaching a build checkout. The Docker build context
uses a deny-by-default allowlist, and the Dockerfile copies only runtime source,
templates, static source, and migrations. It excludes the historical database,
SQL dumps, environment files, credentials, local data, logs, caches, tests, and
the demo seed command from the image. Recheck the built image contents before
any service is connected to a database. Do not rewrite Git history or delete
the historical file as part of this packaging task.

A local aggregate-only classification found non-empty employee, asset, and
authentication-user tables, including usable password hashes. No row values
or hashes were displayed. Treat the historical file as possibly real and
potentially credential-bearing; the external build/connect gate remains on
hold until the manager resolves repository and credential exposure.

## Build and start behavior

The image build installs the pinned project requirements and Gunicorn 26.2.0,
then runs `collectstatic` in `DJANGO_ENV=build` with a disposable `/tmp` SQLite
path. It does not run migrations, seed demo data, create users, or use
`DATABASE_URL`. Normal startup executes one Gunicorn process with two threads
and a 60-second timeout, bounded for a single 512 MB free instance. The image
sets fail-closed production environment defaults and runs as an unprivileged
UID. The
`/health/` endpoint is configured as the service health check.

Normal startup never migrates. A future migration must be a separate,
explicitly authorized maintenance operation from an operator-controlled
environment after the storage and isolation checks. Before that operation, take and
verify an independent database backup, review the migration plan and current
database state (including the duplicate-identifier preflight), and schedule an
approved maintenance window. Do not attach migration commands or migration
environment gates to automatic startup, and do not use a free expiring database
for durable inventory.

## Required external environment

Set these on the service only after the authorized operator confirms credentials
and isolation for the approved schema:

- `DJANGO_ENV=production`
- `DJANGO_DEBUG=false`
- `DJANGO_DB_ROLE=runtime`
- `ASSET_DB_SCHEMA=assets_portfolio`
- `DJANGO_SECRET_KEY`: a generated secret of at least 50 characters
- `DJANGO_ALLOWED_HOSTS`: whitespace-separated hostnames, without schemes
- `DJANGO_CSRF_TRUSTED_ORIGINS`: whitespace-separated `https://` origins
  whose hostnames are listed in `DJANGO_ALLOWED_HOSTS`
- `DATABASE_URL`: the approved existing Supabase connection scoped to the
  private `assets_portfolio` schema; supplied by its authorized operator

The secret and deployment-specific values are marked `sync: false`; they are
not committed in `render.yaml`. Use the app's assigned `onrender.com` hostname
in the host and origin settings. Do not use sample secrets, SQLite, an
unisolated/shared schema, or values from local `.env` files.

## Free-tier limits and open gates

Render's [Free web services](https://render.com/docs/free) spin down after
15 minutes without inbound traffic and have an ephemeral filesystem. Free
PostgreSQL is limited to 1 GB, expires after 30 days, and has no backups. It is
preview-only and must never hold durable production records. This is not the
selected storage target. Restart persistence and recovery have not been
demonstrated. No paid fallback has been authorized.

Before any external deployment, obtain the authorized operator's confirmation
that the existing schema and credentials are isolated from unrelated projects
and data, review the image contents and credential exposure risk, establish backup and
restore procedures suitable for the selected storage, and perform an approved
end-to-end hosting review. These checks are not satisfied by this Blueprint.
Any cloud DDL or schema migration remains reserved to the designated operator;
this packaging task does not create a database or apply migrations.

Blueprint fields follow Render's current
[Blueprint specification](https://render.com/docs/blueprint-spec), and the
container packaging follows its [Docker deployment documentation](https://render.com/docs/docker).
