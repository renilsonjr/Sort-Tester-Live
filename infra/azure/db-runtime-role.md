# Runtime database role — audit H-3 / Task 4

Status: prepared for review and tested locally; **not applied to Azure**.
Related: [[container-apps-app]], [[../../docs/superpowers/plans/2026-11-15-security-remediation]].

## Separate two jobs

The migration owner creates/alters tables and runs `backend.db.upgrade_app`.
The app uses a different PostgreSQL role (`sort_app`) that can read/write app
data but cannot create/alter tables or edit migration bookkeeping. This is a
password role until #84 replaces database passwords with managed identity.

`db-role.sql` creates a **new NOLOGIN role**, with no administrator, role-creation,
database-creation, replication, bypass-RLS or inherited-role privileges. It
refuses a wrong database/owner and an existing role. Its transaction rolls
back on error. It does not remove or modify any existing role.

The script excludes `alembic_version` and `tooling_probe` from existing-table
grants. Future table/sequence privileges apply to objects created by the
specified migration owner; another migration identity needs a separate review.
If PUBLIC already grants schema CREATE, the script refuses rather than changing
every user's access. Inspect and review that old grant before retrying.

## Before any Azure write

The owner first confirms the exact staging server/database, current migration
owner and runtime username, fictional-only data, and whether `sort_app` already
exists. Existing roles must be inspected; do not drop or repurpose one to make
this script succeed. Review the resulting resource changes before deploying.

Use PostgreSQL connection environment variables in a private Cloud Shell:
`PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGSSLMODE=verify-full`, and the CA
bundle in `PGSSLROOTCERT`. `PGUSER` must be the migration owner and `PGDATABASE`
the application database. Enter `PGPASSWORD` with a hidden prompt, on its own
line, then export it; do not put a password or DSN in a command argument.

```sh
read -rsp 'Migration owner password: ' PGPASSWORD
export PGPASSWORD
psql -X -v ON_ERROR_STOP=1 -c "SELECT current_database(), current_user; SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls FROM pg_roles WHERE rolname = 'sort_app';"
```

## Prepare the role — owner executes after reviewing the reads

From the repository root, set non-secret shell variables `APP_DATABASE` and
`MIGRATION_ROLE` to the exact values just verified. Then:

```sh
psql -X -v target_database="$APP_DATABASE" -v migration_role="$MIGRATION_ROLE" \
  -v runtime_role=sort_app -f infra/azure/db-role.sql
```

The new role cannot log in yet. Open an interactive `psql -X` session as the
migration owner; run `\password sort_app` and enter a generated password from
the password manager at its hidden prompts. Then run:

```sql
ALTER ROLE sort_app LOGIN;
```

Exit psql and `unset PGPASSWORD` when the owner connection is no longer needed.
Keep the migration identity separate; never grant its membership to `sort_app`.

## Deploy and verify — still pending

1. Prepare the runtime URL using `sort_app` and verified TLS. Supply secrets
   through a restricted, untracked parameter file or the reviewed secret store,
   never command-line literals. Do not reuse the migration URL for runtime.
2. Inspect `az deployment group what-if` for the exact existing app/environment
   and expected secret/revision changes. Stop on unexpected deletes/replacements.
   Deployment remains an owner-run operation under [[container-apps-app]].
3. Deploy the reviewed change. On staging, check health, register/login, Ranked
   start → answer → quit → settled result, and the owner flow with fictional data.
4. With the runtime identity, confirm `CREATE TABLE` / `ALTER TABLE` and writes
   to `alembic_version` are refused. Run schema migrations only with the migration
   identity. A no-op migration at head is not proof of denied DDL.
5. Record the active revision, runtime role name, checks and timestamp without
   passwords. Keep Task 4 incomplete until this evidence exists.

No registry, Key Vault, network, resource creation, or employee-data rollout is
included here. Those have separate tasks, costs and operational checks.

## Local verification — 2026-11-16

Scratch PostgreSQL tests execute the actual psql script, confirm wrong-target
refusal, exercise account INSERT/SELECT/UPDATE/DELETE and the HTTP register →
login → me → logout flow under SET ROLE, and confirm DDL/metadata access is
refused. Future table/sequence grants and refusal to alter an existing role
are also checked. SET ROLE verifies SQL permissions; it does not prove Azure
password authentication, networking, TLS or deployment.
