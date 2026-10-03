# Asset schema proposal: inaccessible extension objects — 2026-10-03

Historical candidate: `2026-10-03-failed-outside-table-11d46f2e.sql`, a byte-for-byte copy of `deploy/assets-isolation-proposal.sql` at SHA-256 `11D46F2E62B85E6FEC062E74F0A8E0F23C346769E07BA2C6784C01CFE3FD8F61`.

The sole external Supabase operator reported that the proposal reached its precommit outside-table assertion and rolled back. The reported matches were `extensions.pg_stat_statements` and `extensions.pg_stat_statements_info`: `PUBLIC` grants `SELECT` on those objects, while `assets_portfolio_app` has no `USAGE` on the `extensions` schema. No table rows were read in this review. The live catalog and transaction result remain the operator's evidence; this review did not execute SQL or inspect the database.

PostgreSQL 17 requires schema `USAGE` in addition to object privileges to access an object in a schema. The superseding proposal therefore checks both schema `USAGE` and object privileges for outside tables and sequences, in its precommit assertions and matching postcommit diagnostics. It does not change `PUBLIC`, extension, or unrelated project ACLs. The existing database/schema `CREATE` and callable `SECURITY DEFINER` checks remain.

The superseding SQL remains unexecuted after this correction. Preserve this record when interpreting later operator results.
