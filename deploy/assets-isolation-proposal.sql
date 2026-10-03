-- REVIEW PROPOSAL ONLY. This file has not been executed against Supabase.
-- Target project: psusviqzkhlslmieuotb; dedicated private schema: assets_portfolio.
-- The transaction creates the schema only when absent; an existing namespace is a stop condition.
-- No SQLite data is copied.
-- Create role passwords separately through a protected provider/secret interface.
-- Never paste database credentials into this file, chat, build arguments, or Git.

BEGIN;

DO $preflight$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_roles
        WHERE rolname IN ('assets_portfolio_owner', 'assets_portfolio_app')
    ) THEN
        RAISE EXCEPTION 'One or both dedicated asset roles already exist; stop and review their ownership and grants.';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'assets_portfolio') THEN
        RAISE EXCEPTION 'Schema assets_portfolio already exists; stop and review its owner and contents.';
    END IF;
END
$preflight$;

CREATE ROLE assets_portfolio_owner
    LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
CREATE ROLE assets_portfolio_app
    LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;

GRANT CONNECT ON DATABASE postgres TO assets_portfolio_owner, assets_portfolio_app;
ALTER ROLE assets_portfolio_owner SET search_path = assets_portfolio, pg_catalog;
ALTER ROLE assets_portfolio_app SET search_path = assets_portfolio, pg_catalog;

-- Temporarily grant the verified SQL SESSION_USER only enough membership to SET ROLE
-- as the owner. The grant is non-inheriting, exists only inside this transaction,
-- and is explicitly revoked before COMMIT. No persistent operator membership remains.
GRANT assets_portfolio_owner TO CURRENT_USER
    WITH ADMIN TRUE, INHERIT FALSE, SET TRUE;
CREATE SCHEMA assets_portfolio AUTHORIZATION assets_portfolio_owner;
SET LOCAL ROLE assets_portfolio_owner;

-- The owner role is used only by an explicit, one-off migration operation.
-- The web process must use assets_portfolio_app, which cannot create/alter schema objects.
REVOKE ALL ON SCHEMA assets_portfolio FROM PUBLIC, anon, authenticated, service_role;
GRANT USAGE ON SCHEMA assets_portfolio TO assets_portfolio_app;

-- Keep Data API roles and PUBLIC out of this application's private schema.
REVOKE ALL ON ALL TABLES IN SCHEMA assets_portfolio FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA assets_portfolio FROM PUBLIC, anon, authenticated, service_role;
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA assets_portfolio FROM PUBLIC, anon, authenticated, service_role;

-- Django migrations create objects as the dedicated owner. Runtime receives DML only.
ALTER DEFAULT PRIVILEGES FOR ROLE assets_portfolio_owner IN SCHEMA assets_portfolio
    REVOKE ALL ON TABLES FROM PUBLIC, anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES FOR ROLE assets_portfolio_owner IN SCHEMA assets_portfolio
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO assets_portfolio_app;
ALTER DEFAULT PRIVILEGES FOR ROLE assets_portfolio_owner IN SCHEMA assets_portfolio
    REVOKE ALL ON SEQUENCES FROM PUBLIC, anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES FOR ROLE assets_portfolio_owner IN SCHEMA assets_portfolio
    GRANT USAGE, SELECT ON SEQUENCES TO assets_portfolio_app;
ALTER DEFAULT PRIVILEGES FOR ROLE assets_portfolio_owner IN SCHEMA assets_portfolio
    REVOKE EXECUTE ON FUNCTIONS FROM anon, authenticated, service_role;
-- Per-schema default revokes cannot cancel a global PUBLIC EXECUTE default. Revoke it
-- globally for this new, dedicated migration role only; do not alter shared-role defaults.
ALTER DEFAULT PRIVILEGES FOR ROLE assets_portfolio_owner
    REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

-- Fail before COMMIT if the runtime role can reach outside data or create objects
-- through an inherited/direct grant. PUBLIC USAGE on shared schemas is reported below
-- but is not globally revoked here. Dangerous SECURITY DEFINER calls also block commit.
RESET ROLE;
DO $effective_privilege_check$
BEGIN
    IF NOT has_schema_privilege('assets_portfolio_app', 'assets_portfolio', 'USAGE')
       OR has_schema_privilege('assets_portfolio_app', 'assets_portfolio', 'CREATE') THEN
        RAISE EXCEPTION 'Runtime role must have USAGE and no CREATE on assets_portfolio; transaction rolled back.';
    END IF;

    IF has_database_privilege('assets_portfolio_app', current_database(), 'CREATE') THEN
        RAISE EXCEPTION 'Runtime role has database CREATE privilege; transaction rolled back.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_namespace n
        WHERE n.nspname NOT IN ('assets_portfolio', 'pg_catalog', 'information_schema')
          AND has_schema_privilege('assets_portfolio_app', n.oid, 'CREATE')
    ) THEN
        RAISE EXCEPTION 'Runtime role has CREATE privilege outside assets_portfolio; transaction rolled back.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname NOT IN ('assets_portfolio', 'pg_catalog', 'information_schema')
          AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
          AND (has_table_privilege('assets_portfolio_app', c.oid, 'SELECT')
               OR has_table_privilege('assets_portfolio_app', c.oid, 'INSERT')
               OR has_table_privilege('assets_portfolio_app', c.oid, 'UPDATE')
               OR has_table_privilege('assets_portfolio_app', c.oid, 'DELETE'))
    ) THEN
        RAISE EXCEPTION 'Runtime role has table privileges outside assets_portfolio; transaction rolled back.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname NOT IN ('assets_portfolio', 'pg_catalog', 'information_schema')
          AND c.relkind = 'S'
          AND (has_sequence_privilege('assets_portfolio_app', c.oid, 'USAGE')
               OR has_sequence_privilege('assets_portfolio_app', c.oid, 'SELECT')
               OR has_sequence_privilege('assets_portfolio_app', c.oid, 'UPDATE'))
    ) THEN
        RAISE EXCEPTION 'Runtime role has sequence privileges outside assets_portfolio; transaction rolled back.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname NOT IN ('assets_portfolio', 'pg_catalog', 'information_schema')
          AND p.prosecdef
          AND has_schema_privilege('assets_portfolio_app', n.oid, 'USAGE')
          AND has_function_privilege('assets_portfolio_app', p.oid, 'EXECUTE')
    ) THEN
        RAISE EXCEPTION 'Runtime role can execute an outside-schema SECURITY DEFINER function; transaction rolled back.';
    END IF;
END
$effective_privilege_check$;

-- Restore the SQL editor's original principal and remove temporary SET/ADMIN access.
REVOKE assets_portfolio_owner FROM CURRENT_USER;
DO $membership_cleanup_check$
BEGIN
    IF pg_has_role(SESSION_USER, 'assets_portfolio_owner', 'SET') THEN
        RAISE EXCEPTION 'Temporary owner SET membership remains; transaction rolled back.';
    END IF;
END
$membership_cleanup_check$;

COMMIT;

-- OPERATOR FOLLOW-UP (outside this SQL file):
-- 1. Generate separate strong passwords for the two LOGIN roles in the approved secret manager.
-- 2. Apply them through a protected database/provider interface; do not put literals in SQL/Git.
-- 3. Runtime URL uses the Supavisor SESSION pooler on port 5432 and user
--    assets_portfolio_app.psusviqzkhlslmieuotb. Migration URL uses the owner role and is separate.
-- 4. Verify actual current_user, current_schema(), current_setting('search_path'), grants, and
--    that an existing table outside assets_portfolio cannot be selected by the runtime role.
-- 5. Review effective PUBLIC function execution below. Do not revoke shared PUBLIC privileges
--    or alter the Polarus schema/grants as part of this isolated setup.

-- Read-only acceptance diagnostics. Review every returned row before app deployment.
SELECT n.nspname AS outside_schema,
       has_schema_privilege('assets_portfolio_app', n.oid, 'USAGE') AS can_use,
       has_schema_privilege('assets_portfolio_app', n.oid, 'CREATE') AS can_create
FROM pg_namespace n
WHERE n.nspname NOT IN ('assets_portfolio', 'pg_catalog', 'information_schema')
  AND (has_schema_privilege('assets_portfolio_app', n.oid, 'USAGE')
       OR has_schema_privilege('assets_portfolio_app', n.oid, 'CREATE'))
ORDER BY n.nspname;

SELECT n.nspname AS outside_schema,
       c.relname AS object_name,
       c.relkind AS object_kind,
       has_table_privilege('assets_portfolio_app', c.oid, 'SELECT') AS can_select,
       has_table_privilege('assets_portfolio_app', c.oid, 'INSERT') AS can_insert,
       has_table_privilege('assets_portfolio_app', c.oid, 'UPDATE') AS can_update,
       has_table_privilege('assets_portfolio_app', c.oid, 'DELETE') AS can_delete
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname NOT IN ('assets_portfolio', 'pg_catalog', 'information_schema')
  AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
  AND (has_table_privilege('assets_portfolio_app', c.oid, 'SELECT')
       OR has_table_privilege('assets_portfolio_app', c.oid, 'INSERT')
       OR has_table_privilege('assets_portfolio_app', c.oid, 'UPDATE')
       OR has_table_privilege('assets_portfolio_app', c.oid, 'DELETE'))
ORDER BY n.nspname, c.relname;

SELECT n.nspname AS outside_schema,
       p.oid::regprocedure AS function_name,
       p.prosecdef AS security_definer,
       has_function_privilege('assets_portfolio_app', p.oid, 'EXECUTE') AS can_execute
FROM pg_proc p
JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname NOT IN ('assets_portfolio', 'pg_catalog', 'information_schema')
  AND has_schema_privilege('assets_portfolio_app', n.oid, 'USAGE')
  AND has_function_privilege('assets_portfolio_app', p.oid, 'EXECUTE')
ORDER BY n.nspname, p.oid::regprocedure::text;

SELECT has_schema_privilege('anon', 'assets_portfolio', 'USAGE') AS anon_schema_usage,
       has_schema_privilege('authenticated', 'assets_portfolio', 'USAGE') AS authenticated_schema_usage,
       has_database_privilege('assets_portfolio_app', current_database(), 'CREATE') AS app_database_create,
       has_database_privilege('assets_portfolio_app', current_database(), 'TEMP') AS app_temporary_objects;

SELECT c.relname AS private_schema_object,
       has_table_privilege('anon', c.oid, 'SELECT') AS anon_select,
       has_table_privilege('anon', c.oid, 'INSERT') AS anon_insert,
       has_table_privilege('anon', c.oid, 'UPDATE') AS anon_update,
       has_table_privilege('anon', c.oid, 'DELETE') AS anon_delete,
       has_table_privilege('authenticated', c.oid, 'SELECT') AS authenticated_select,
       has_table_privilege('authenticated', c.oid, 'INSERT') AS authenticated_insert,
       has_table_privilege('authenticated', c.oid, 'UPDATE') AS authenticated_update,
       has_table_privilege('authenticated', c.oid, 'DELETE') AS authenticated_delete
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'assets_portfolio'
  AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
  AND (has_table_privilege('anon', c.oid, 'SELECT,INSERT,UPDATE,DELETE')
       OR has_table_privilege('authenticated', c.oid, 'SELECT,INSERT,UPDATE,DELETE'))
ORDER BY c.relname;

SELECT c.relname AS outside_sequence,
       has_sequence_privilege('assets_portfolio_app', c.oid, 'USAGE') AS can_use,
       has_sequence_privilege('assets_portfolio_app', c.oid, 'SELECT') AS can_select,
       has_sequence_privilege('assets_portfolio_app', c.oid, 'UPDATE') AS can_update
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname NOT IN ('assets_portfolio', 'pg_catalog', 'information_schema')
  AND c.relkind = 'S'
  AND (has_sequence_privilege('assets_portfolio_app', c.oid, 'USAGE')
       OR has_sequence_privilege('assets_portfolio_app', c.oid, 'SELECT')
       OR has_sequence_privilege('assets_portfolio_app', c.oid, 'UPDATE'))
ORDER BY n.nspname, c.relname;
