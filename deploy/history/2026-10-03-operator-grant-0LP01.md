# Asset schema proposal: failed operator grant — 2026-10-03

Historical candidate: `2026-10-03-failed-0LP01-902c9630.sql`, byte-for-byte copy of `deploy/assets-isolation-proposal.sql` at SHA-256 `902C9630C53133CF38FA990BE29377E2BB904B91EE62FE359B81451CE431EAD5`.

The sole external Supabase operator reported SQLSTATE `0LP01`, “ADMIN option cannot be granted back to your own grantor,” at `GRANT assets_portfolio_owner TO CURRENT_USER WITH ADMIN TRUE, INHERIT FALSE, SET TRUE`. The operator verified that the transaction rolled back atomically and committed no dedicated roles or schema. This note records the operator's report; this review did not execute SQL or inspect the cloud database.

PostgreSQL 17 automatically gives a non-superuser `CREATEROLE` creator a bootstrap-granted `ADMIN TRUE, INHERIT FALSE, SET FALSE` membership on each newly created role. The creator cannot alter or revoke that bootstrap grant. The superseding proposal requests a separate operator-granted `SET TRUE` membership with `ADMIN FALSE`, uses it to create the owner-authorized schema and perform owner ACL operations, then revokes the temporary grant and checks that `SET` access is gone before commit. The bootstrap `ADMIN` membership remains.

The SQL proposal remains unexecuted after this correction. Its new SHA-256 and independent review belong in the current release handoff; do not treat this historical failure note as evidence of a successful migration.
