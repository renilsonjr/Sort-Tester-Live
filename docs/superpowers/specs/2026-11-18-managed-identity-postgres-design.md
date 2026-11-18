# Managed-identity authentication to PostgreSQL — design (#84)

Design for [issue #84](https://github.com/renilsonjr/Sort-Tester-Live/issues/84):
let the hosted app authenticate to PostgreSQL as its managed identity, so
no database password exists to store, leak or rotate.

## Scope of this work

**This preparation ships code, tests and a written runbook. It deploys
nothing and changes no Azure resource, grant or server setting.** The
production app stays on password authentication, unchanged, until a
separately-approved deployment under its own review. The token path is
built behind an off-by-default flag so merging it cannot alter the running
app.

In scope:

- The Python token-authentication path (`settings.py`, a new token module,
  `pool.py`), behind a mode flag defaulting to `password`.
- Tests for token reuse, refresh, the failure path, and the guarantee that
  no token value is ever logged.
- A runbook section: the Entra role/grants mapping SQL (written, not
  applied), the token-as-password connection, and a tested rollback.

Out of scope (later review, not this PR):

- `container-apps-app.bicep` changes.
- Any deployment, grant change, or Entra role creation in Azure.
- Disabling server-wide `passwordAuth`.
- Removing the runtime password reference from Key Vault.

## What changes, and what does not

This changes **how the app authenticates to the database**, not how anyone
uses the app.

- **Today:** the app connects with a password. It is held in Key Vault,
  read by the app's managed identity, used to connect as the least-
  privilege `sort_app` role over a private endpoint with verified TLS. The
  password exists in two places (a password manager and the vault) and is
  rotated by hand.
- **After #84 (deployed, separately):** the app requests a short-lived
  Entra access token (refreshed roughly hourly) and uses it in place of the
  password. No runtime database password exists.

Unchanged by this work: player/owner login and every app route and screen;
local development (stays on password, needs no Azure); the runtime role's
privileges (still runtime-only, no DDL/migration); the **administrator**
password, which is a separate credential the owner holds and has chosen not
to rotate; and migrations/tests, which connect through `migrate.connect`,
not the pool.

## Architecture

Four seams, each testable on its own.

### 1. Mode selection (`backend/db/settings.py`)

A new environment variable `SORT_TESTER_DB_AUTH` selects the runtime
authentication mode:

- `password` (default) — current behaviour exactly. Dev and CI stay here.
- `managed_identity` — the app fetches an Entra token per physical
  connection.

A helper `db_auth_mode()` reads and validates it; an unknown value raises
`DatabaseConfigError` at startup rather than falling back silently. In
`managed_identity` mode the DSN carries **no password**; the database user
is the identity's Entra role, and the identity's client id comes from
`SORT_TESTER_DB_IDENTITY_CLIENT_ID`. TLS validation (`require`/`verify-ca`/
`verify-full`) and the statement timeout apply in both modes — the token
path reuses the existing `_require_verified_tls` check.

`app_database_url()` keeps returning the DSN. In `managed_identity` mode the
DSN is expected to be password-free; the password is supplied separately by
the pool at connection time (below), never embedded in this string.

### 2. Token provider (`backend/db/entra_token.py`, new)

A small module wrapping `azure.identity.ManagedIdentityCredential`.

- `DB_TOKEN_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"`.
- A module-level credential, built lazily from
  `SORT_TESTER_DB_IDENTITY_CLIENT_ID`, with a setter seam
  (`set_credential(...)`) so tests inject a fake and no test touches Azure.
- `db_access_token() -> str` calls `credential.get_token(DB_TOKEN_SCOPE)`
  and returns `.token`. `azure-identity` caches the token internally and
  only contacts the IMDS endpoint when the cached token is near expiry, so
  "reuse within lifetime" and "refresh before expiry" come from the SDK; we
  do not reimplement a cache.
- **The token value is never logged.** The module logs nothing containing
  it; failures log the error type, not the token. A test enforces this.
- On acquisition failure the exception propagates to the pool/connection
  layer, which decides the HTTP outcome (below). The module does not retry
  in a loop.

### 3. Pool integration (`backend/db/pool.py`)

`init_pool(conninfo, *, auth_mode=...)` gains the mode.

- `password` mode: unchanged. The pool is built from the conninfo exactly
  as today.
- `managed_identity` mode: the pool obtains a **fresh token as the password
  for each physical connection it opens or replaces**, using
  `psycopg_pool` 3.3.3's per-connection callable connection parameter (the
  exact API — a callable `kwargs` value vs. a `configure`/`connection_class`
  seam — is pinned in the implementation plan; whichever is used, the token
  is resolved at physical-connect time, not baked into the startup DSN).
  `sslmode`, `row_factory` and `statement_timeout` are identical to the
  password path; the username is the identity's Entra role.

The pool keeps its bounded size (`MAX_SIZE = 8`), `check_connection` health
check, and the explicit-transaction `checkout()` contract — none of that
changes. Because the token is fetched per physical connection and the SDK
caches it, a burst does not fetch N tokens; it reuses the cached one.

### 4. Failure path → clean 503

When token acquisition or a physical connect fails, the pool cannot produce
a new connection and `getconn` raises (bounded by the pool's acquisition
timeout — no retry spin). The request path translates that specific
failure-to-create into an **HTTP 503** with a generic message, distinct
from an unexpected 500, and **with no token or DSN in the message or log**.

- Existing healthy connections keep serving; only requests that need a
  *new* connection while tokens are unavailable get the 503.
- A single, explicit translation point (a dependency or handler wrapping
  `checkout()`), so the behaviour is one tested place, not scattered.
- The pool's `check=check_connection` already discards dead connections;
  this adds only the acquisition-failure → 503 mapping.

## Data flow

```
request ──> checkout() ──> pool.getconn()
                               │
                 password mode │ existing conn or new conn (DSN password)
                               │
          managed_identity ────┤ new physical conn needed?
                               │     └─> db_access_token()  (SDK cache; IMDS only near expiry)
                               │           └─> connect(user=<entra role>, password=<token>, sslmode=…)
                               │
         token/connect fails ──┴─> getconn raises ──> handler maps to HTTP 503 (no secret logged)
```

## Testing

All tests run with a fake credential; none contacts Azure. CI stays in
`password` mode for its own database; these tests set `managed_identity`
locally within the test and inject the fake.

1. **Reuse within lifetime** — two physical connections in one window call
   the credential's `get_token` the number of times the SDK's cache implies
   (the fake records calls; a token valid for the window is fetched once and
   reused).
2. **Refresh near expiry** — the fake returns a token near expiry, then a
   fresh one; the second physical connection uses the new token.
3. **Failure path** — `get_token` raises; a request needing a new
   connection receives 503, there is no retry loop (bounded call count), and
   healthy connections are unaffected.
4. **No token in logs** — capture logging during acquisition, success and
   failure; assert no token substring appears anywhere.
5. **Mode validation** — unknown `SORT_TESTER_DB_AUTH` raises
   `DatabaseConfigError` at startup; `managed_identity` with a password in
   the DSN is rejected (the password must not be embedded).
6. **Password mode untouched** — the existing pool/auth tests stay green;
   `password` remains the default with no new required env var.

## Runbook (written, not applied)

A new section in `infra/azure/container-apps-app.md` (or the role doc),
clearly marked as a procedure gated on separate approval:

- **Role/grants mapping SQL** — map the *existing* user-assigned managed
  identity to a PostgreSQL Entra role with runtime-only privileges (no
  superuser, no `CREATE`, no DDL, no migration authority), mirroring the
  current `sort_app` grants. Verifying the actual mapping and grants is a
  checklist item; existing registry/vault access is **not** database access.
- **Connection** — the token as the connection password for the scope
  above, `sslmode=verify-full` where the image carries a CA bundle (Task 7
  dependency noted), else `require`.
- **Rollback** — the tested path back to `password` mode: flip
  `SORT_TESTER_DB_AUTH`, confirm the vault password reference still works,
  on a new revision (a restart does not re-read the secret — runbook §9b).
- **Ordered deploy/verification** — all behind owner approval, no step run
  as part of this work: deploy with the flag, verify login/reconnect/
  refresh on the hosted identity, verify admin/migration still work through
  their intended Entra path, and only then consider removing the runtime
  password reference and (separately, with approval) server-wide
  `passwordAuth`.

## Dependencies

- `azure-identity` (and its transitive `azure-core`) pinned by version in
  `backend/requirements-runtime.txt`. This is the one runtime-image size
  cost of the change.
- Needs the hosted app (#41, done). Should land before employee data (#13).
  Parent roadmap: #1.

## Risks and limits

- The exact `psycopg_pool` 3.3.3 per-connection-parameter API is confirmed
  during planning against the pinned version; if the callable-kwarg form is
  not available, the `connection_class`/`configure` seam is the fallback,
  with the same "token resolved at physical connect" property.
- This design is verified by tests and the written runbook only. Live
  identity login, reconnect and refresh are **not** proven here — that is
  the separately-approved deployment, explicitly out of scope.
- `verify-full` depends on the image's CA bundle (Task 7 step 3); the
  runbook records `require` as the floor if that is not yet verified at
  cutover.
