# Runtime database role — audit H-3 / Task 4

Status: applied to fictional-data Azure staging on 2026-11-16; runtime and owner checks verified.
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

## Deployment procedure

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

## Azure verification — 2026-11-16

Applied the reviewed role SQL from PR #155 after explicit owner approval.
Migrations 0021–0035 ran under the migration identity; schema 0035 was verified.
The owner entered the runtime password directly at hidden Cloud Shell prompts,
then approved enabling LOGIN. No password or login ID is recorded here.

The actual app secret authenticates as `sort_app` with `sslmode=verify-full`
and the system CA bundle. TLS was confirmed active. CREATE TABLE, ALTER TABLE,
and UPDATE of `alembic_version` were refused with insufficient privileges;
test transactions were rolled back. This tests the DDL/metadata operations a
migration needs: running a no-op upgrade at head would not prove separation.

The initial deployment succeeded. A later image-only update serves merged
PR #156, source `e1b644b8a8a84ba48573f0760c98e26c7a0da084`, digest
`sha256:b60d5a8e6c1bd4eda985d33fffa2891a01ce118c75b2cb30f3731df60e0a2cde`.
The update preserved the full app configuration. Published HTML, auth module
and home image match source; health is 200 and anonymous session access 401.

Hosted HTTP smoke passed registration, login, session lookup, normal Ranked
start → heartbeat → question → answer → quit → result, and logout. A separate
fictional promotion fixture was seeded at the Iron cap, then answered all 15
questions through HTTP: Iron 1000 → Bronze 1001. Repeated result and quit
calls returned the same settlement; the database contained exactly one
settlement for that attempt. The fixture remains test data, not player progress.
The normal attempt, promotion, and DDL checks used the actual runtime role.

The owner confirmed successful login and access to Owner tools in the published
interface. Database verification found exactly one owner, matching the approved
account. This verifies access, not every privileged action. Only Pre-Season
exists; no official season was launched. Hosted promotion was tested over HTTP,
not as a complete mobile browser journey. Load, restore, network isolation and
employee rollout remain separate checks under #13 and [[security-foundation]].

Removed agent-created secret parameter/deployment-result files from Cloud Shell.
[Image publication evidence](https://github.com/renilsonjr/Sort-Tester-Live/actions/runs/43831986133).

## Managed-identity mode (#84) — applied to staging, password NOT yet removed

Status: **applied to fictional-data Azure staging on 2026-11-19.** The Entra
role `id-sort-app-stg` was mapped with runtime-only grants (DDL denied,
verified), and the app was cut over to `managed_identity` on a new revision.
Hosted login, token refresh across the token lifetime, the clean-503 failure
path and a tested rollback were all verified. The runtime **password reference
has deliberately NOT been removed**: the `database-url` secret stays as the
rollback credential, and server-wide `passwordAuth` stays enabled, pending the
owner's separate approval. The procedure below records what was done and what
remains gated.

### What the code does

The app selects its mode with `SORT_TESTER_DB_AUTH` (`password`, the default,
or `managed_identity`). In managed-identity mode the connection password is a
fresh Entra token the app fetches per physical connection and caches until near
expiry; the DSN carries **no password**, the database user is the Entra role,
and TLS stays `verify-full` where the image's CA bundle is confirmed (Task 7
step 3), else `require`. The app reuses the existing user-assigned managed
identity; its client id is supplied as `SORT_TESTER_DB_IDENTITY_CLIENT_ID`.
Token or connection failure returns a clean HTTP 503 with no secret logged.

The token is fetched at the **hosting platform's identity endpoint**: Azure
Container Apps (and App Service) inject `IDENTITY_ENDPOINT` and
`IDENTITY_HEADER`, used with api-version `2019-08-01` and the
`X-IDENTITY-HEADER` header. The app falls back to the VM IMDS address only when
those are absent. Container Apps does **not** expose the VM IMDS endpoint
(`169.254.169.254`); an earlier build that only knew IMDS failed there with a
`URLError` (fixed in PR #231).

**The passwordless DSN must set `sslrootcert=system`.** With `sslmode=verify-full`
and no `sslrootcert`, libpq looks for `~/.postgresql/root.crt`, which is not in
the image, and every connection fails with `root certificate file ... does not
exist`. The password-mode secret DSN already carries `sslrootcert=system`; the
managed-identity DSN must too. The working runtime value is:

```
postgresql://id-sort-app-stg@<server>.postgres.database.azure.com:5432/<app_database>?sslmode=verify-full&sslrootcert=system
```

### Map the identity to a least-privilege Entra role — reviewed, not applied

Connect to the application database as the server's **Entra administrator**
(not the password admin), in a private Cloud Shell, with verified TLS. First
verify the exact server, database and the identity's object id against the
reviewed values; do not proceed on a guessed name or id.

The mapping creates an Entra-authenticated role for the existing identity and
grants it the **same runtime privileges as `sort_app` and no more** — read and
write app data, `USAGE` on sequences, and no superuser, `CREATE`, DDL or
migration authority. Using non-secret shell variables set to the verified
values (`$MI_ROLE` the new role name, `$MI_OBJECT_ID` the identity's object id,
`$APP_DATABASE` the application database):

```sql
-- As the Entra administrator, in the application database:
SELECT pgaadauth_create_principal_with_oid(:'mi_role', :'mi_object_id', 'service', false, false);

-- Mirror the sort_app runtime grants exactly; grant nothing the migration
-- owner holds. Review db-role.sql and keep this list identical to it.
GRANT CONNECT ON DATABASE :"app_database" TO :"mi_role";
GRANT USAGE ON SCHEMA public TO :"mi_role";
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO :"mi_role";
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO :"mi_role";
-- Keep alembic_version and tooling_probe OUT of the runtime grants, as
-- db-role.sql does; revoke if the ALL-TABLES grant included them.
REVOKE ALL ON alembic_version, tooling_probe FROM :"mi_role";
```

These grants cover the tables that exist when they are run and **nothing
created afterwards**: unlike `db-role.sql`, this mapping sets no default
privileges. Every later migration that creates a table must grant it to the
role by hand before the new image is deployed — [[container-apps-app]] §1d-i.

Then **verify the actual mapping and grants against the live server** —
existing registry and Key Vault access the identity already holds is not
database access and must not be assumed to grant it. Confirm the role cannot
`CREATE TABLE`, `ALTER TABLE`, or write `alembic_version`, exactly as the
password role was verified above.

### Rollback to password mode — tested before the forward cutover

Set `SORT_TESTER_DB_AUTH=password` (or unset it) and confirm the Key Vault
password reference still resolves as the `sort_app` DSN. Apply the change on a
**new revision** — a restart does not re-read the vault secret (see
[[container-apps-app]] §9b). Exercise this rollback and confirm the app serves
on the password credential before the forward cutover is trusted.

### Ordered deploy and verification — gated on separate owner approval

None of these is run as part of preparing this work:

1. Deploy with `SORT_TESTER_DB_AUTH=managed_identity` and the identity client
   id set; the runtime DSN carries no password but **must keep
   `sslmode=verify-full&sslrootcert=system`** (see "What the code does").
2. Verify hosted identity login, reconnect after an idle period, and a token
   refresh across the token lifetime; database-dependent requests return 503
   only when no connection can be made, never a logged secret.
3. Verify administrator and migration access still work through their intended
   Entra path; the migration identity stays separate from the runtime role.
4. Only after the above, and separately approved: remove the runtime password
   reference from Key Vault, and consider disabling server-wide `passwordAuth`
   after confirming administrator/migration access through its Entra path.

This does not approve the employee pilot (#13), expand Azure access, or
authorise any deployment.
