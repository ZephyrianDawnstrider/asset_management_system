# Asset schema proposal: event-trigger function — 2026-10-03

Historical candidate: `2026-10-03-failed-outside-secdef-595664c9.sql`, a byte-for-byte copy of `deploy/assets-isolation-proposal.sql` at SHA-256 `595664C9BC703FCC014200FD880B6A2E982B5D4BD37BE4C1247E0B259D8B72AA`.

The sole external Supabase operator reported an atomic rollback at the precommit outside-schema `SECURITY DEFINER` assertion. The root operator's live metadata check identified the only match as `public.rls_auto_enable()`: zero arguments, `SECURITY DEFINER`, return type `pg_catalog.event_trigger`, and fixed `pg_catalog` search path. This review did not execute SQL or inspect the cloud database.

PostgreSQL 17 requires superuser privilege to create event triggers. The superseding proposal excludes only functions with `pg_catalog.event_trigger` return type from the callable-function precommit assertion and its matching diagnostic. Ordinary trigger functions remain covered. No shared function, role, or ACL was changed by this source repair.

The superseding SQL remains unexecuted after this correction. Preserve this failed-candidate record alongside the earlier role-grant and inaccessible-extension-object histories.
