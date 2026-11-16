-- Run with psql as the migration owner. No password is accepted by this file.
-- Required psql variables: target_database, migration_role, runtime_role.
-- Creates a NEW role only; errors roll back all grants and role creation.
\set ON_ERROR_STOP on
SELECT current_database() = :'target_database'
   AND current_user = :'migration_role' AS correct_target \gset
\if :correct_target
\else
  DO $$ BEGIN RAISE EXCEPTION 'Refused: database or migration owner does not match.'; END $$;
\endif

BEGIN;
CREATE ROLE :"runtime_role" NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
  NOREPLICATION NOBYPASSRLS NOINHERIT;

-- Older databases may grant schema CREATE to PUBLIC. Refuse rather than
-- silently changing privileges for every other role on the database.
SELECT has_schema_privilege(:'runtime_role', 'public', 'CREATE') AS unsafe_create \gset
\if :unsafe_create
  ROLLBACK;
  DO $$ BEGIN RAISE EXCEPTION 'Refused: PUBLIC grants schema CREATE. Review that grant separately.'; END $$;
\endif

GRANT CONNECT ON DATABASE :"target_database" TO :"runtime_role";
GRANT USAGE ON SCHEMA public TO :"runtime_role";
-- Migration bookkeeping and the tooling probe are not runtime app data.
SELECT format('GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE %I.%I TO %I',
              schemaname, tablename, :'runtime_role')
FROM pg_tables WHERE schemaname = 'public'
  AND tablename NOT IN ('alembic_version', 'tooling_probe')
\gexec
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO :"runtime_role";

-- These defaults apply only to objects subsequently created by this
-- migration owner. Run migrations with this same owner in the future.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"runtime_role";
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE ON SEQUENCES TO :"runtime_role";
COMMIT;
\echo 'Role prepared with NOLOGIN. Set its password securely before enabling LOGIN.'
