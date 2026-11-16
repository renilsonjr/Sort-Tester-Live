# Sort-Tester-Live Security Remediation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> This plan mixes two task kinds. **Code tasks** (marked `TDD`) follow test-first steps inside the repo. **Ops/infra tasks** (marked `OPS`) change Bicep, SQL, GitHub settings, or Azure resources; their steps are exact commands or edits with a verification result instead of a unit-test loop.

**Goal:** Close every Critical/High finding and the prioritized Medium/Low findings from the 2026-11-15 security audit, so the app is safe to hold real (non-fictional) data on Azure.

**Architecture:** FastAPI monolith (one container serves frontend + `/api`) on Azure Container Apps (Consumption, 1 replica), PostgreSQL Flexible Server (pre-existing, outside IaC), private GHCR images, raw SQL via psycopg through `backend/db/migrate.py` helpers. Single-tenant: one `is_owner` account, many player accounts; isolation is account-to-account access control enforced at routers and (increasingly) in the schema.

**Tech Stack:** Python 3.14, FastAPI 0.162, psycopg 3.3.8, Alembic 1.20, Pydantic v2, vanilla-JS frontend, Bicep, GitHub Actions.

**Spec:** The security audit delivered in conversation on 2026-11-15 (4 parallel audit agents + first-hand verification of every Critical/High finding). This plan is **self-contained**: the "Findings Index" below is the spec — each task cites the finding ID it implements, with the exact file:line evidence already verified.

**Repo:** this one (all code tasks run from its root unless a step says otherwise).

---

## Historical planning note — 2026-11-16, before PRs #151–#156

The audit was delivered on 2026-11-15. The following snapshot was captured before the fixes in PRs #151–#156; it is historical, not a claim that these bugs still reproduce on the deployed source. Current Task 4 evidence is recorded in its task section and [[../../../infra/azure/db-runtime-role]]. At planning time:

1. **H-1 still reproduces.** `backend/routers/auth.py:88-93` and `backend/routers/ranked.py:83-88` open a connection, call `get_account_by_session` (which UPDATEs `last_seen_at`, and revokes on idle) and close it without `conn.commit()` — psycopg rolls both back. `_purge_pending_deletions` (`auth.py:75-80`) is the same bug class: accepted deletions are never actually purged. `test_auth_sessions.py` passes because it holds one connection open across the call, so the uncommitted write is still visible inside that transaction — which is why Task 1 asks for a **router-level** regression test.
2. **"Existing defenses to keep" #2 needs rewording, not restoring.** `correct_belt` now leaves the server in one place on purpose: the answer response, *after* the answer is graded and recorded (PR #148, issue #95 prerequisite). The invariant that still holds is **"the right belt is never readable before the answer is accepted"** — `current_question` returns only the four offered belts, and a tie-break reveals nothing until the round closes. Do not "fix" the feedback screen back out of existence.
3. **New stored state to keep in scope.** `assignment_questions.options` (migration 0035) stores the four belts each question offers. The belts are drawn with `secrets.SystemRandom` and stored precisely so they are not derivable from anything a player can see; Task 19's FK sweep should cover this table too.

One correction to Task 6, Step 2: the private DNS zone is `privatelink.postgres.database.azure.com` (the plan text reads `privelink`, which would silently fail to resolve).

## Getting started (read once before any task)

Backend tests need a PostgreSQL scratch database:

```sh
export SORT_TESTER_TEST_DATABASE_URL="postgresql://<user>:<pw>@<host>:5432/sort_tester_unittest_scratch"
backend/.venv/bin/python -m unittest discover -s backend/tests -v   # backend suite
node --test tests/*.test.mjs                                        # browser/frontend suite
```

The suite also runs on Windows in CI (`security-regression.yml`), so no platform-specific code. Single-test run: `backend/.venv/bin/python -m unittest backend.tests.test_auth_sessions -v`.

## Global Constraints

- All SQL goes through `backend/db/migrate.py` helpers with `%s` placeholders — never f-strings/format/concatenation.
- Integrity belongs in the schema (CHECK / UNIQUE / FK / trigger), not only app code — this is the project's own convention; new invariants follow it.
- Uniform refusals: missing vs. foreign resources get the identical 404/401 — never introduce an existence oracle.
- No secrets in tracked files or on the CLI; runbook parameters go through `read -rsp` or an untracked `@file`.
- GitHub Actions stay SHA-pinned; deployable images are referenced by digest only.
- Migrations stay a strictly linear chain: the new file's `down_revision` is the current head, and the chain has exactly one head.
- Tag `'data-classification': 'fictional-only'` stays until the Phase 0 exit gate is signed off.
- Don't weaken anything in the "Existing defenses to keep" list at the end of this plan.

## Review Focus (failure modes the findings imply — each pinned to the task that tests it)

1. **Any future auth path that opens its own DB connection forgets to commit** (the H-1 bug class — writes silently roll back on `conn.close()`). Pinned: Task 1 adds a router-level regression test and a commit-coverage sweep of every `_db_connection` call site.
2. **A proxy misconfiguration re-globalizes the rate limiter** (all clients share one bucket). Pinned: Task 2 tests key-by-target behavior; Task 3 tests the bicep default; `test_auth_rate_limit.py` already A/B tests X-Forwarded-For trust.
3. **A DSN without TLS is silently accepted** (config drift undoes M-4). Pinned: Task 7's test feeds `postgresql://u:p@h/db` with no `sslmode` and asserts startup refusal.
4. **The season-row `FOR UPDATE` serialization sneaks back** (M-2 regression). Pinned: Task 12 keeps `test_ranked_races.py` green and adds a no-lock early-return test.
5. **A schema migration forks the chain** (two heads). Pinned: Task 19 ends with a "exactly one head" verification step.

---

## Findings Index (the spec)

| ID | Severity | Location (verified) | One-line summary | Task |
|---|---|---|---|---|
| H-1 | High | `backend/routers/auth.py:87-95`, `backend/routers/ranked.py:82-90`, `backend/auth/sessions.py:71-78` | Session `last_seen_at` refresh + idle revocation are never committed — every session dies 15 min after login; revocations don't persist | 1 |
| H-2 | High | `backend/auth/rate_limit.py:64-67,122-130`, `infra/azure/container-apps-app.bicep:53` | Default `trustedProxies=''` → one shared bucket behind the ingress: anonymous global login/sign-up DoS; success resets brute-force counter | 2, 3 |
| H-3 | High | `infra/azure/container-apps-app.md:111` → bicep `databaseUrl` | App runs as the PostgreSQL **server admin** | 4 |
| H-4 | High | `container-apps-app.md:208-211`, no VNet in bicep | `AllowAzureServices` 0.0.0.0 firewall: every Azure tenant can reach TCP 5432; password is the only barrier | 6 |
| H-5 | High | `container-apps-app.bicep:33-38,103-108`, `container-apps-app.md:165-171` | Registry pull with account-scoped `read:packages` PAT (pulls any private package) | 5 |
| M-1 | Med | `backend/routers/ranked.py:55-79,824-825` | Public `/season/notice` runs the full lock-heavy sweep chain per request; 2nd unpooled connection per auth request | 11 |
| M-2 | Med | `backend/ranked/tiebreaks.py:926-935` | `FOR UPDATE` on the season row before the early-return → all requests serialize forever | 12 |
| M-3 | Med | `backend/ranked/scoring.py:69-73`, `migrations/0008:33` | No points floor/cap → `smallint` overflow permanently bricks an account's settlement | 13 |
| M-4 | Med | `backend/db/settings.py:72-81` | No `sslmode` enforcement in code; deploy uses `require` (no server-cert verification) | 7 |
| M-5 | Med | `backend/db/migrate.py:36,39-62` | No pool (fresh connection per call, ×2 per request) + savepoint round trips per statement | 14 |
| M-6 | Med | `container-apps-app.md:181-185,227-229` | Runbook types PAT + DB URL inline on the CLI (shell history / `ps`) | 15 |
| M-7 | Med | `.github/workflows/app-image-publish.yml:14-46` | Publish has no environment gate; any write-access collaborator, any branch | 8 |
| M-8 | Med | `.github/workflows/` (absence) | No secret scanning, dependency review, `pip-audit`, or Dependabot | 9 |
| M-9 | Med | `infra/azure/spike.Dockerfile:7-10`, `app-image.yml:199-200` | Spike image ships dev deps publicly; Trivy runs with Docker socket + mutable tag | 10 |
| M-10 | Med | `migrations/0008:48-52`, `0006:29-30`, `0030:30-33` | Missing same-account composite FKs (ledger↔settlement, attempts↔assignments, tiebreak_attempts↔attempts) — the class 0023 fixed | 19 |
| L-all | Low | see audit §2 "Low / quick wins" | launch re-auth, cookie default, ticket cap, origin-guard Host trust, session lifecycle, pagination, reviewer `deleted_at`, login race guard, duplicate indexes, `tooling_probe`, `season_prizes` cap, real server name in docs | 16, 17, 18, 19, 15 |
| P-items | Plan | audit §3 | resource locks, bicep lint, log ingestion, rotation runbook, owner questions | 20, 21, 22 |

**Not found / already correct (do not re-audit, do not weaken):** no BOLA/IDOR across all 34 routes, no SQL injection, no mass assignment, no answer exposure (`correct_belt` never leaves the server), no stored XSS, no error-detail leaks, no committed secrets, SHA-pinned CI, digest-only deploys, non-root hardened image, timing-parity login, DB-enforced single-owner and one-credential rules, atomic settlement, uniform 404s.

---

## Phase 0 — Must fix before real data (P0)

Tasks 1–3 are code fixes (fast, independent). Tasks 4–7 are Azure changes (can start in parallel; 4 and 7 land before 6).

### Task 1: Persist session writes — fix the uncommitted `last_seen_at` / idle-revocation bug (H-1) — `TDD`

**Files:**
- Modify: `backend/routers/auth.py:87-95` (`_current_account`)
- Modify: `backend/routers/ranked.py:82-90` (`_current_account`)
- Verify (read first): `backend/auth/deletion.py` (`request_deletion` — confirm it commits internally; `delete_account` at `routers/auth.py:259-290` shows no explicit commit)
- Test: `backend/tests/test_auth_sessions.py` (extend)

**Interfaces:**
- Consumes: existing `get_account_by_session(conn, raw_token)`, `_db_connection()`.
- Produces: unchanged public behavior; both `_current_account` helpers commit before the connection closes. No other task depends on new names.

- [ ] **Step 1: Write the failing regression tests** (through the HTTP layer, against the scratch DB, in the existing test style)

```python
def test_last_seen_at_advances_across_authenticated_requests(self):
    # register + login via the test client; read the session row:
    #   SELECT last_seen_at FROM sessions WHERE token_hash = ...
    # then GET /api/auth/me, sleep briefly (or inject clock), re-read:
    #   assert second > first          <- fails today (rollback)

def test_idle_revocation_persists_after_refusal(self):
    # login; UPDATE sessions SET last_seen_at = now() - interval '16 minutes'
    # GET /api/auth/me -> 401
    # re-read row: assert revoked_at IS NOT NULL   <- fails today (rollback)
```

- [ ] **Step 2: Run them and verify they fail** — `backend/.venv/bin/python -m unittest backend.tests.test_auth_sessions -v` → both FAIL.
- [ ] **Step 3: Fix both helpers identically**

```python
with _db_connection() as conn:
    account = get_account_by_session(conn, raw_token)
    conn.commit()  # persist the last_seen_at refresh / idle revocation
```

If `request_deletion` does not commit internally, add the same `conn.commit()` to `delete_account` and extend its test to assert the row landed.

- [ ] **Step 4: Sweep the bug class:** `grep -n "_db_connection" backend/ -r` — every `with` block that writes through `migrate.execute` must commit (login `auth.py:144`, logout `:167`, reauth `:250` already do). Fix any others found; one test each.
- [ ] **Step 5: Full suites pass** — backend unittest + `node --test tests/*.test.mjs`.
- [ ] **Step 6: Commit** — `security: commit session idle-refresh and revocation writes (audit H-1)`

### Task 2: Rate-limiter hardening — key by client+target, stop resetting on success (H-2, code half) — `TDD`

**Files:**
- Modify: `backend/auth/rate_limit.py:64-67` (`record_success`)
- Modify: `backend/routers/auth.py:124-141` (login), `:232-235` (reauth), `:274-277` (delete) — switch to the new key
- Create: helper `def _login_rate_key(request, login_id: str) -> str` in `backend/auth/rate_limit.py`
- Test: `backend/tests/test_auth_rate_limit.py` (extend)

**Interfaces:**
- Produces: `_login_rate_key(request, login_id) -> str` — `f"{_client_key(request)}|{target}"` where `target` is `derive_lookup_key(login_id)` on valid input, the literal `"invalid"` when `derive_lookup_key` raises `ValueError`. Registration limiter keeps plain `_client_key` (its global 200/day cap is by design).

- [ ] **Step 1: Failing tests:**
  1. 10 failures against login ID A from one client → 11th attempt for A gets 429, while a login for ID B from the same client is still allowed.
  2. Interleave 10 failures on A with 10 **successes** on the attacker's own ID → the counter for A is NOT reset; next A attempt gets 429.
  3. Malformed login ID → key falls back to `"invalid"`, no 500.

- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement.** `record_success` zeroes the bucket instead of deleting it (`bucket.failures = 0`); login/reauth/delete use `_login_rate_key`.
- [ ] **Step 4: Suite passes (includes the existing X-Forwarded-For trust A/B tests — they must stay green).**
- [ ] **Step 5: Commit** — `security: key login limiter by client+credential, expire buckets instead of resetting (audit H-2)`

### Task 3: Deployment default trusts the ingress for client addresses (H-2, config half) — `OPS`

**Files:**
- Modify: `infra/azure/container-apps-app.bicep:47-53`
- Modify: `infra/azure/container-apps-app.md` (§5b note + §1 runbook step for the #78 check)
- Test: `backend/tests/test_azure_container_app.py` (extend: assert the param is required or default `'1'`)

- [x] **Step 1: Verify the ACA ingress appends the real client address** (runbook issue #78 check — one request with a spoofed `X-Forwarded-For` while the app logs the computed client key; with `SORT_TEST_TRUST_PROXY=1` the spoofed first entry must be ignored). Record the result in the runbook.
- [x] **Step 2: Make the safe value explicit** — change the param so the template cannot deploy with the unsafe default:

```bicep
@allowed(['1'])   // one trusted proxy: the ACA ingress
param trustedProxies string = '1'
```

- [x] **Step 3: Update `test_azure_container_app.py`** to pin the new param contract; run `backend/.venv/bin/python -m unittest backend.tests.test_azure_container_app -v` → PASS.
- [x] **Step 4: `az bicep build --file infra/azure/container-apps-app.bicep --stdout >/dev/null`** → exits 0.
- [x] **Step 5: Commit** — `security: require trustedProxies=1 now that ingress XFF is verified (audit H-2)`

Implementation note — 2026-11-16: Step 1 uses the staging evidence recorded
in `container-apps-app.md` on 2026-11-14, not a new cloud verification. The
parameter retains a default of `1` for existing deployment commands and allows
only `1`; explicit empty/`2` overrides are rejected. Runtime deployment is
separate from this repository change.

Verification: 18 template/rate-limit tests passed with local scratch PostgreSQL;
Bicep CLI 0.49.2 compiled the template and the emitted JSON was checked for
`allowedValues: ['1']`, `defaultValue: '1'` and app environment wiring. No Azure
deployment or new live ingress probe ran. Task 3 repository work is ready for
PR review; deployment evidence remains with #41/#13.

### Task 4: Least-privilege database role (H-3) — `OPS`

**Files:**
- Create: `infra/azure/db-role.sql` (tracked — it contains no secrets)
- Modify: `infra/azure/container-apps-app.md` (§1: app DSN now uses `sort_app`; migrations keep the admin DSN; add the rotation note)

- [x] **Step 1: Create the role as the admin, against `sort_tester_app`:**

```sql
CREATE ROLE sort_app LOGIN PASSWORD '<generated in password manager>';
GRANT CONNECT ON DATABASE sort_tester_app TO sort_app;
GRANT USAGE ON SCHEMA public TO sort_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO sort_app;
GRANT USAGE ON ALL SEQUENCEs IN SCHEMA public TO sort_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO sort_app;   -- run as the admin (migration) role
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE ON SEQUENCES TO sort_app;
```

- [x] **Step 2: Redeploy the app secret** with the `sort_app` DSN (runbook §4/§5, parameters via the new `@file` method from Task 15). `az deployment group what-if` → exactly the expected `2 to modify`, zero Delete/Replace.
- [x] **Step 3: Verify the app works with reduced rights:** `/health` 200; register; login; start + answer + quit an attempt (exercises INSERT/UPDATE on accounts, sessions, attempts, answers, settlements, balance_history); owner path if reachable. Then confirm a **migration** with the runtime DSN fails loudly (expected `permission denied`) — proving separation — while `upgrade_app` with the admin DSN succeeds.
- [x] **Step 4: Commit the SQL + runbook update** — `security: dedicated sort_app DML role for the runtime, admin reserved for migrations (audit H-3)`

Task 4 verified — 2026-11-16: PR #155 SQL and runbook were merged;
Azure migrations reached 0035 under the migration identity, and the deployed
app now authenticates as `sort_app` with verifying TLS. Health, registration,
login, normal start/answer/quit/result and complete promotion HTTP checks passed.
The owner confirmed access to Owner tools. Runtime CREATE/ALTER and migration
metadata UPDATE were denied. See [[../../../infra/azure/db-runtime-role]] for
source/digest and evidence limits. The DDL/metadata checks replace a misleading
no-op upgrade-at-head test; no test migration was applied to staging.

### Task 5: Registry pull via ACR + managed identity (H-5) — `OPS`

**Files:**
- Modify: `infra/azure/container-apps-app.bicep` (add the dedicated user-assigned identity + ACR registry entry; delete `registryUsername`/`registryPassword` params and the `registry-password` secret)
- Modify: `.github/workflows/app-image-publish.yml` (also push the digest to ACR) and `container-apps-app.md` §2/§3
- Test: `backend/tests/test_azure_container_app.py` (update: no registry password param; identity present)

- [x] **Step 1: Create the registry** — `az acr create -g rg-sort-tester-staging -n <name> --sku Standard` (uses the verified student free allowance; recheck its quota and expiry first) (name is not a secret; track it in the private inventory, not the runbook).
- [ ] **Step 2: Publish path** — extend the publish workflow to push the same digest to ACR (repo settings: add an `ACR` environment or use the existing publish gate from Task 8; authenticate with a short-lived token via `az acr login` in the job, not a stored PAT). Manual interim: `az acr import --source ghcr.io/renilsonjr/sort-tester-live-app@sha256:<digest> ...`.
- [ ] **Step 3: Bicep changes** — after the identity bootstrap is approved: attach the dedicated user-assigned runtime identity to the container app and use its resource ID in the registry entry; remove both registry params and the secret entry.
- [x] **Step 4: Bootstrap runtime read access** — after explicit approval of the identity and both scopes, register the ManagedIdentity provider if needed and deploy `runtime-identity.bicep`. Its resource-scoped AcrPull and Key Vault Secrets User assignments reference the new identity principal. Verify the resolved principal and exact direct assignments before later app association. No publisher or subscription-wide role belongs to the runtime.
- [ ] **Step 5: Move the database secret into Key Vault (audit §3 P0-1)** — the dedicated vault already exists. Prepare a separately reviewed operator write path and transfer the limited-role DSN through an in-memory or protected-file method, never a command argument. The identity bootstrap grants read access only; it does not grant an operator secret-write access. Verify its existing vault read binding rather than adding a duplicate. In the app Bicep, replace the inline secret value with the Key Vault URI and runtime identity reference, then remove the `databaseUrl` parameter only after the tested transition/rollback path is ready.
- [ ] **Step 6: Verify:** app pulls and boots; `az containerapp show` config contains no registry password and no inline DB secret; GHCR PAT is **revoked**.
- [ ] **Step 7: Update tests + runbook; commit** — `security: ACR + managed identity + Key Vault; PAT and inline DB secret retired (audit H-5, §3 P0-1)`

Task 5 foundation applied — 2026-11-16: PR #157 merged; the owner approved
only student-credit/free-allowance-covered usage. Refreshed credit, Enabled
student subscription, spendingLimit On, and create-only what-if were verified.
ACR Standard and the empty RBAC Key Vault Standard were created. The first
vault create rejected explicit purge-protection false; the corrected template
omits it, and the remaining-vault-only deployment succeeded. Postchecks verified
registry auth flags/zero repositories, vault settings/no direct role assignments,
unchanged app configuration and spending protection. See
[[../../../infra/azure/security-foundation]] for exact evidence and API limits.
At the foundation checkpoint only Step 1 was complete; the vault-creation
portion of Step 5 was complete, but
publishing, secret transfer, app switch and PAT retirement remain pending;
the later approved identity bootstrap is recorded below. No overall Task 5
completion or rollout approval is claimed.

Task 5 identity preparation — 2026-11-16: [[../../../infra/azure/runtime-identity]]
and its Bicep prepare one user-assigned identity plus AcrPull on the dedicated
registry and Key Vault Secrets User on the dedicated vault. This refines the
original system-assigned example so grants can precede app changes, following
Azure's image-pull recommendation. Compiled scope/principal checks and negative
mutations passed; Azure what-if showed three Creates and no existing-resource
changes. At preparation time Microsoft.ManagedIdentity was NotRegistered.
This preparation itself neither authorized nor executed provider registration,
identity/grant creation or app association. Separate owner approval of these
exact accesses was required before execution.

Task 5 identity bootstrap applied — 2026-11-16: after explicit owner approval
and PR #159 merge `5bb7194`, the merged JSON matched the reviewed hash. Student
subscription/spending protection and absent identity were rechecked; provider
registration reached Registered. Fresh what-if showed only the same three
Creates. Deployment `sort-runtime-identity-5bb7194` succeeded. Actual identity
and subscription assignment inventory verified the expected principal and
exactly the two resource-scoped roles; details are in [[../../../infra/azure/runtime-identity]].
Full app resource remained equal to its snapshot, no identity is attached,
health was HTTP 200, spendingLimit On. Only Step 4 is newly complete; no
functional image-pull/secret-read or whole Task 5 completion is claimed.

### Task 6: Network isolation — VNet-injected environment + private endpoint (H-4) — `OPS` *(biggest change: plan a deployment window)*

**Files:**
- Modify: `infra/azure/container-apps-app.bicep` (VNet-injected `appEnvironment`, private endpoint for the DB)
- Create: VNet/subnet + private DNS zone resources (in this template or a sibling `network.bicep`)
- Modify: `container-apps-app.md` (new §5a replacing the 0.0.0.0 rule; teardown §8 updated)

- [ ] **Step 1: Owner decisions (blocking):** subnet CIDR for the ACA environment, whether the spike/staging apps retire first (recommended — they're disposable), downtime window (environment recreate).
- [ ] **Step 2: Create network:** VNet + delegated subnet (`Microsoft.App/environments`), private DNS zone `privelink.postgres.database.azure.com` linked to the VNet, private endpoint on the Flexible Server targeting its `postgresqlServer` group ID.
- [ ] **Step 3: Update the bicep** — `appEnvironment.properties.vnetConfiguration` with the subnet resourceId; the DB URL host stays the server FQDN (resolved privately inside the VNet).
- [ ] **Step 4: Redeploy per runbook (parameters via `@file`); what-if clean.**
- [ ] **Step 5: Acceptance checks:**
  - App boots, `/health` 200, login + one attempt flow works (DB reachable privately).
  - **Delete the `allow-azure-services` rule** (`az postgres flexible-server firewall-rule delete … --name allow-azure-services`) and confirm the app still works.
  - From outside Azure: `psql` to the server FQDN times out (public access disabled); only the migration firewall rule opens temporarily per runbook §1.
- [ ] **Step 6: Commit + runbook** — `security: VNet-injected environment + DB private endpoint, public firewall rule removed (audit H-4)`

### Task 7: Enforce TLS on every DSN, verify the server certificate (M-4 + audit L1) — `TDD`

**Files:**
- Modify: `backend/db/settings.py:67-81` (`app_database_url`) and `:18-54` (`test_database_url`) — validate effective `sslmode`
- Create: `infra/azure/postgres-ca.pem` (public Azure PostgreSQL root CA — not a secret)
- Modify: `infra/azure/app.Dockerfile` (COPY the PEM to `/app/postgres-ca.pem`), `container-apps-app.md` (DSN gains `sslmode=verify-full&sslrootcert=/app/postgres-ca.pem`)
- Test: `backend/tests/test_db_settings.py` (extend)

**Interfaces:**
- Produces: `app_database_url()` raises `DatabaseConfigError` unless the effective `sslmode` (after libpq defaults) is `verify-full`, `verify-ca`, or `require`; absent `sslmode` is **rejected** (libpq would default to `prefer`). `test_database_url()` applies the same rule **except** when the resolved host is loopback (`127.0.0.1`, `::1`, `localhost`) — local dev Postgres without SSL stays usable. Error messages name the required values.

- [ ] **Step 1: Failing tests:** DSN without `sslmode` → `DatabaseConfigError`; `sslmode=disable`/`allow`/`prefer` → rejected; `require`/`verify-full` → accepted (parse with `conninfo_to_dict`, mirroring the existing validation style).
- [ ] **Step 2: Run → FAIL. Implement in `settings.py` (both functions).**
- [ ] **Step 3: Bake the CA + update the deploy DSN** as above; `docker build` locally and confirm the file is present (`docker run --rm <img> ls -l /app/postgres-ca.pem`).
- [ ] **Step 4: Redeploy; verify** the app connects (verify-full succeeds only with the right CA) and the DSN validation refuses a tampered `sslmode` at startup.
- [ ] **Step 5: Suites pass; commit** — `security: fail closed on DSNs without verified TLS (audit M-4/L1)`

**Phase 0 exit gate (real-data bar):** Tasks 1–7 done; full backend + node suites green; Trivy gate green; `what-if` clean; staging smoke (register/login/attempt/owner flow) passes; owner signs off — only then may the `fictional-only` tag change.

---

## Phase 1 — Pipeline integrity (independent of Phase 0 code tasks)

### Task 8: Publish environment gate (M-7) — `OPS`

- Modify: `.github/workflows/app-image-publish.yml` — add `environment: publish` to the publish job.
- Repo settings (manual): create environment `publish`, required reviewers = the owner, deployment branch policy = `main` (+ `codex/ranked-mode` while it is the working branch).
- Add a guard step in the job: `if github.ref not in allowed refs → fail fast` (belt-and-braces alongside the environment policy).
- Verify: dispatch from a disallowed branch is rejected; a dispatch from an allowed branch waits for approval; expected reviewers listed in the run.
- Commit — `security: require publish environment approval and branch policy (audit M-7)`

### Task 9: Secret scanning + dependency review + pip-audit (M-8) — `OPS`

- Create: `.github/workflows/security-gates.yml` — on push/PR: gitleaks (action SHA-pinned); on PR: `actions/dependency-review` (SHA-pinned); a `pip-audit` job installing `pip-audit` and running `pip-audit -r backend/requirements-runtime.txt` (dev set too if desired; runtime first).
- Create: `.github/dependabot.yml` — `pip` ecosystem watching `backend/`, plus `github-actions` ecosystem (both update the pinned digests by PR).
- One-time provenance review (blocking question for the owner): the dev-only packages `httpx2`, `httpcore2`, `fastar`, `agent-detector`, `fastapi-cloud-cli` in `backend/requirements.txt` — none ship in the runtime image, but they execute in CI; confirm publisher/provenance or drop them from the dev set.
- Repo settings (manual): enable secret scanning + push protection.
- Verify: workflow runs green on the opening PR; push protection blocks a test commit containing a fake `AKIA…`-style key (try on a scratch branch).
- Commit — `security: secret scanning, dependency review, pip-audit, Dependabot (audit M-8)`

### Task 10: Digest-pin CI images, slim the spike image (M-9) — `OPS`

- Modify: `.github/workflows/app-image.yml:199-200` — replace `aquasec/trivy:0.76.2` with `aquasec/trivy@sha256:<digest>` (get it: `docker manifest inspect aquasec/trivy:0.76.2`); same treatment for the `postgres:18-alpine` service image.
- Modify: `infra/azure/spike.Dockerfile:7-10` — build from `backend/requirements-runtime.txt`; delete the `--upgrade setuptools/msgpack` hack.
- Modify: `infra/azure/app.Dockerfile.dockerignore:13-24` — re-ignore `backend/requirements.txt` and `backend/tests/**` so only the runtime manifest and app code ship in the app image (audit L4).
- Verify: spike workflow builds and its `/health` probe passes; Trivy step still gates HIGH/CRITICAL; digest recorded in the workflow file.
- Commit — `security: digest-pinned CI images, spike image on runtime deps only (audit M-9)`

---

## Phase 2 — Resilience (start after Task 1; Tasks 11–14 are independent of each other)

### Task 11: Public endpoint off the sweep chain (M-1) — `TDD`

**Files:**
- Modify: `backend/routers/ranked.py:55-79` (keep `get_db` as-is for authenticated routes), `:824-825`
- Create in the same file: `def get_readonly_db():` — `with _db_connection() as conn: yield conn` (no sweeps)
- Test: `backend/tests/test_ranked_leaderboard_router.py` or a new `test_season_notice.py`

**Interfaces:**
- Produces: `get_readonly_db` — plain connection dependency for read-only public routes.

- [ ] **Step 1: Failing test:** `/api/ranked/season/notice` returns correct data while **no sweep function runs** (monkeypatch `finish_due_seasons`/`close_due_rounds`/`purge_due_cases`/`purge_deleted_accounts` to raise; endpoint must still answer — currently fails because `get_db` calls them).
- [ ] **Step 2: Implement:** `season_notice` takes `conn=Depends(get_readonly_db)`.
- [ ] **Step 3: Sweeps still run on authenticated routes** — assert one authenticated ranked call invokes the sweep chain (existing tests largely cover this; add one explicit assertion).
- [ ] **Step 4 (optional, only if load tests show need):** in-process sweep throttle behind `SORT_TESTER_SWEEP_INTERVAL_SECONDS` (default `0` = current behavior) — never changes semantics, only frequency.
- [ ] **Step 5: Suites pass; commit** — `security: read-only dependency for public season notice, sweeps off the anonymous path (audit M-1)`

### Task 12: Lock-free early return in `finalize_prizes` (M-2) — `TDD`

**Files:**
- Modify: `backend/ranked/tiebreaks.py:926-935`
- Test: `backend/tests/test_ranked_prize_finalization.py` (extend)

- [ ] **Step 1: Failing test:** season already final → second call returns `"final"` **without** any `FOR UPDATE` (monkeypatch/observe: e.g., assert via a second connection holding the row lock that the call still completes — currently blocks/fails).
- [ ] **Step 2: Implement:** lock-free `SELECT phase, frozen_at, prizes_final_at, closes_at, closed_at FROM seasons WHERE id = %s` first; return early unless the row is an unfrozen-pending official season; only then re-select `FOR UPDATE` and re-check (double-checked locking — the row can change between reads).
- [ ] **Step 3: `test_ranked_races.py` + prize finalization tests pass unchanged (concurrency semantics preserved).**
- [ ] **Step 4: Commit** — `security: finalize_prizes checks before locking, not under lock (audit M-2)`

### Task 13: Points bounds — no more smallint brick (M-3) — `TDD` + `OPS`

**Files:**
- Modify: `backend/ranked/scoring.py:69-73` (clamp in `settle`)
- Create: `backend/migrations/versions/0035_points_bounds.py`
- Test: `backend/tests/test_ranked_scoring.py` (extend), new schema test in `test_db_balance_ledger_schema.py` style

- [ ] **Step 0 (owner decision, blocking):** confirm negative balances are a legitimate game state (wrong answers deduct, so yes per current rules) → bounds are `±30000`, not `>= 0`.
- [ ] **Step 1: Failing tests:** `settle(points_before=30000, …quit)` → `points_after == 29990` (stays in range); `settle(points_before=-30000, …quit)` → floor holds; settlement of a clamped result succeeds against a `smallint` column.
- [ ] **Step 2: Implement clamp:** after computing `points_after` for partial outcomes, `points_after = max(min(points_after, 30000), -30000)`.
- [ ] **Step 3: Migration 0035** (down_revision = `0034`): `ALTER TABLE balances ADD CONSTRAINT balances_points_range CHECK (current_points BETWEEN -30000 AND 30000)`; same for `balance_history.adjustment, points_before, points_after` (bounds wide enough for the clamp: `adjustment BETWEEN -60000 AND 60000`).
- [ ] **Step 4: Verify single head:** `backend/.venv/bin/python -c "from backend.db import migrate, settings; print(migrate.current_revision(settings.test_database_url()))"` → `0035`; full suite green.
- [ ] **Step 5: Commit** — `security: clamp settled points and add schema bounds (audit M-3)`

### Task 14: Connection pool + statement timeout (M-5) — `TDD`

**Files:**
- Create: `backend/db/pool.py`
- Modify: `backend/routers/auth.py:27-33`, `backend/routers/ranked.py:44-52` (`_db_connection` uses the pool)
- Modify: `backend/requirements-runtime.txt` (+ pinned `psycopg-pool`, added via the documented freeze procedure in that file's header), `backend/requirements.txt`
- Test: new `backend/tests/test_db_pool.py`

**Interfaces:**
- Produces: `backend.db.pool`: `init_pool(conninfo: str) -> None` (idempotent, called at app startup / first use), `@contextmanager def checkout() -> psycopg.Connection` (commits on clean exit, rolls back on exception, returns to pool). Pool `max_size=8`, DSN gains `options=-c statement_timeout=5000`. Tests keep using `migrate.connect` directly — the pool is a router-layer concern only.

- [ ] **Step 1: Failing test:** two concurrent `checkout()` calls reuse one connection object after release (identity check) — no pool today, so a fresh `connect` each time fails it.
- [ ] **Step 2: Implement `pool.py`; swap both routers' `_db_connection` to `checkout()`.** Note the commit-on-exit semantics replace Task 1's explicit `conn.commit()` inside `_current_account` — keep the tests from Task 1 as the guard that semantics are unchanged.
- [ ] **Step 3: Full suite green** (the app falls back to the test DSN in test environments — `settings.app_database_url()` already handles that).
- [ ] **Step 4: Deploy; verify** under a burst (`for i in $(seq 1 50); do curl -s localhost:8000/api/ranked/season/notice & done` locally, or staging) that response times stay flat and `pg_stat_activity` shows ≤ 8 app connections.
- [ ] **Step 5: Commit** — `security: pooled connections with statement timeout for the runtime (audit M-5)`

### Task 15: Runbook secrets off the CLI + docs hygiene (M-6 + L3) — `OPS`

- Modify: `.gitignore` — add `infra/azure/*.parameters*.json`.
- Modify: `infra/azure/container-apps-app.md:181-185, 227-229` — parameters via `@infra/azure/app.parameters.local.json` (template shown with placeholders; the real file untracked), created with `read -rsp` guidance like §1d.
- Modify: `container-apps-app.md:40` — replace the real server name `pg-sort-tester-rjstg1109` with `<server>` (keep real names in the private inventory only); update `infra/azure/README.md:10-20` so the app template is listed as the live deployable.
- Verify: `git check-ignore infra/azure/app.parameters.local.json` → matches; `git grep pg-sort-tester` → no matches.
- Commit — `security: no secrets on the CLI, no real resource names in tracked docs (audit M-6/L3)`

---

## Phase 3 — Hardening & hygiene (independent tasks; batch the one-liners)

### Task 16: Hardening batch (nine small fixes, one test cycle) — `TDD`

**Files & changes:**
1. `backend/routers/ranked.py:396-433` — `launch_season` gains `request: Request` and calls `_require_recent_reauth(request, conn)` after the owner check (matching `:612, :643, :726, :796`).
2. `backend/auth/settings.py:20` — `cookie_secure: bool = True`; local dev sets `SORT_TESTER_COOKIE_SECURE=false` explicitly (document in `dev/` or README); **or** fail startup when `cookie_secure` is false and `SORT_TESTER_APP_ORIGIN` starts with `https` — pick the startup guard, it cannot be forgotten.
3. `backend/routers/ranked.py:903-906` — `description: str | None = Field(default=None, max_length=2000)`.
4. `backend/support/tickets.py:108-112` — `_require_reviewer` adds `AND deleted_at IS NULL`.
5. `backend/routers/auth.py:142-154` — after login's `get_account_by_session`, `if account is None: raise HTTPException(401, "Unauthorized")` (race guard, no 500).
6. `backend/origin_guard.py:48-53` — when `app_origin` is set, build the allowlist from `app_origin + dev_origins` **only** (request `Host` no longer admitted); Host matching remains the fallback when `app_origin` is unset.
7. `backend/ranked/outages.py:16-38` — `record_outage` gains an `is_owner` check **inside the function**, not in a future caller: it voids attempts and rewrites flags for every account globally and must not remain a bare primitive (audit L5; not wired to any route today).
8. `backend/db/upgrade_app.py:72-81` — `--confirm` must match `dbname@host:port` from `_target()` (not the database name alone), and also refuse the maintenance database `postgres` (audit L7).
9. `backend/db/upgrade_app.py:53-55` — mask any `//user:password@` section in error output with a regex instead of the exact-string replace, so a reformatted DSN cannot leak into deploy logs (audit L8).

- [ ] **Step 1: Failing tests** — one per change where testable: launch without recent reauth → 428 (mirror existing reauth tests); ticket description 2001 chars → 422; reviewer check with soft-deleted owner → 403; login race guard (monkeypatch `get_account_by_session` → None) → 401 not 500; origin guard: write with attacker Host+Origin and `app_origin` configured → 403; startup guard test for cookie_secure; `record_outage` from a non-owner connection → refused; `--confirm` with the right dbname but wrong host → refused; a percent-encoded DSN in an error message is still masked.
- [ ] **Step 2: Implement all six. Step 3: Full suites green.**
- [ ] **Step 4: Commit** — `security: auth hardening batch (launch reauth, cookie default, ticket cap, reviewer/deleted, login race, origin guard)`

### Task 17: Session lifecycle — audit trail, cap, cleanup — `TDD`

**Files:**
- Modify: `backend/routers/auth.py:122-154` (login records `ip_address` via the `_client_key` logic and `user_agent` from the header)
- Modify: `backend/auth/sessions.py:13-34` (`create_session` revokes oldest beyond a cap of 5; add `purge_expired_sessions(conn)`)
- Modify: `backend/routers/ranked.py:76-78` (sweep chain gains `purge_expired_sessions` — `DELETE FROM sessions WHERE expires_at < now() - interval '1 day'`)
- Test: `backend/tests/test_auth_sessions.py` (extend)

- [ ] **Step 1: Failing tests:** 6th login on one account revokes the oldest; expired rows are deleted by the sweep; `ip_address`/`user_agent` populated on login (and never returned by any endpoint — grep response models).
- [ ] **Step 2: Implement. Step 3: Suites green.**
- [ ] **Step 4: Commit** — `security: session audit trail, per-account cap, expired-row cleanup`

### Task 18: Server-side caps on every list (pagination, minimal) — `TDD`

**Files:**
- Modify: `backend/ranked/history.py:36-38`, `backend/support/tickets.py:78-84`, `backend/ranked/standings.py:95-116`, `backend/ranked/flags.py:58-74`, `tickets.py` review queue (add `LIMIT`)

- [ ] **Step 1:** Add a server-enforced `LIMIT` (500 rows history/tickets/standings, 100 for review queues) — no client parameter in this task (a client-set limit is a later, cursor-paginated step; caps first).
- [ ] **Step 2: Failing tests:** insert 600 rows → response has exactly 500 and the newest win (each query already orders).
- [ ] **Step 3: Implement. Step 4: Suites green; frontend list rendering spot-checked against a capped payload.**
- [ ] **Step 5: Commit** — `security: server-side row caps on all list endpoints`

### Task 19: Schema defense-in-depth — composite same-account FKs + cleanup (M-10) — `TDD` + `OPS`

**Files:**
- Create: `backend/migrations/versions/<next>_same_account_keys.py` (down_revision = the current head when you start — `0034`, or `0035` if Task 13 already landed; Phase 2 tasks may land in either order)
- Test: extend the `test_db_*_schema.py` family

- [ ] **Step 1: Migration content (order matters):**
  1. `ALTER TABLE settlements ADD COLUMN account_id uuid NOT NULL` — backfill `UPDATE settlements s SET account_id = a.account_id FROM attempts a WHERE a.id = s.attempt_id`, then `UNIQUE (attempt_id, account_id)`.
  2. `balance_history`: composite FK `(settlement_id, account_id) REFERENCES settlements (attempt_id, account_id)`.
  3. `assignments`: `UNIQUE (id, account_id)`; `attempts`: composite FK `(assignment_id, account_id) REFERENCES assignments (id, account_id)`.
  4. `tiebreak_attempts`: composite FK `(attempt_id, account_id) REFERENCES attempts (id, account_id)` (the `(id, account_id)` key already exists from 0023).
  5. `season_prizes`: add `place smallint NOT NULL CHECK (place BETWEEN 1 AND 3)` with `UNIQUE (season_id, place)` (data is fictional — safe to fix rows by hand if any violate).
  6. `DROP TABLE tooling_probe`; drop duplicate indexes `sessions_token_hash_idx`, `login_credentials_lookup_key_idx`.
- [ ] **Step 2: Schema tests:** each composite FK rejects a cross-account insert; the dropped objects are gone; `place` cap enforced.
- [ ] **Step 3: Verify exactly one head** (`current_revision` → the new head; the chain stays linear) and run the full suite (fictional staging data makes the backfill trivial).
- [ ] **Step 4: Deploy migrations via the guarded admin path (runbook §1d).**
- [ ] **Step 5: Commit** — `security: same-account composite keys across ledger, attempts, tiebreaks (audit M-10)`

### Task 20: Resource locks + Bicep lint in CI — `OPS`

- Modify: `infra/azure/container-apps-app.bicep` — `Microsoft.Authorization/locks@2020-05-01` `CanNotDelete` locks referencing the pre-existing PG server / App Insights / Log Analytics via `existing` resource references (they are outside this template's lifecycle; the lock belongs here precisely because nothing else manages them).
- Modify: `infra/azure/container-apps-spike.bicep:8-10` — constrain `deploymentSuffix` to lowercase alphanumeric (the only unvalidated param in the templates).
- Add to `.github/workflows/security-gates.yml` (Task 9): `az bicep build --file infra/azure/container-apps-app.bicep --stdout >/dev/null` (compile check) + PSRule for Azure or `az deployment group what-if` dry-run job on PRs touching `infra/`.
- Verify: what-if shows only the lock creates; attempting a delete of the DB server is refused by the lock (test in a scratch resource group or trust what-if).
- Commit — `security: CanNotDelete locks on pre-existing shared resources, bicep lint in CI`

---

## Phase 4 — Operational closure

### Task 21: Log ingestion + attack detection — `OPS` *(owner decision: privacy posture was "zero ingestion by design")*

- Modify: `infra/azure/container-apps-app.bicep` — `appEnvironment.properties.appInsightsConfiguration` / Log Analytics wiring to the pre-existing workspace (confirm its retention and access policy with the owner first).
- The app runs uvicorn with `--no-access-log` deliberately — do not turn access logs on. Ingest container stdout/stderr + platform metrics only.
- Add two alert rules: 5xx-rate spike on the app; sustained 429s on `/api/auth/*` (rate-limit lockout storm = the H-2 signature).
- Verify: a forced error appears in the workspace within minutes; alerts fire in a test window.
- Commit — `security: container log ingestion and auth-flood alerting`

### Task 22: Rotation runbook + final verification pass — `OPS`

- Modify: `container-apps-app.md` — add a "Credentials and rotation" section: DB admin password, `sort_app` password, ACR/pipeline tokens — each with generation date, holder, rotation interval (90 days), and the exact rotation commands.
- Final verification (the definition of done, below) executed end-to-end and recorded.
- Commit — `docs: credential rotation runbook; audit remediation complete`

## Owner questions (unverifiable from the repo — answer before Phase 0 sign-off)

1. Flexible Server: `ssl-enforcement` state? Full firewall-rule inventory beyond `allow-azure-services`? `authConfig` (password + Entra) current state?
2. Admin password: generation date, who knows it, rotation plan?
3. Backup/retention configuration on the server; does any backup hold the dropped `emails` data (0021) inside its retention window?
4. Does `sort_tester_app` hold fictional data only, as the tags claim?
5. Game-design decisions: are negative balances intended (drives Task 13 bounds)? Concurrent-session cap of 5 acceptable (Task 17)? List caps (Task 18)?
6. Log ingestion posture (Task 21): accepted, or a documented "no ingestion" risk acceptance?
7. VNet subnet CIDR + downtime window for Task 6; do the spike/staging apps retire?

## Deliberately accepted risks (documented decisions — revisit only if the threat model changes)

1. **Registration 409 "Username taken" oracle** — usernames are public on the leaderboard anyway; hardening it would break the friendly sign-up UX (audit L6).
2. **Tie-break options always include the correct belt** (¼ guess space) — an owner decision recorded in migration 0033 (audit I1).
3. **`serialize_assignment` exports snapshots including answers** — internal/test-only today; the invariant is "never wire it to a router" (audit I2).
4. **Registration limiter keyed by network address only** — the global 200/day cap is the owner's intended backstop; Task 3's `trustedProxies=1` restores per-address granularity.

## Definition of Done (final gate)

- [ ] Tasks 1–22 complete; every commit message references its audit finding ID.
- [ ] `backend/.venv/bin/python -m unittest discover -s backend/tests -v` — green (macOS) and green on the Windows CI job.
- [ ] `node --test tests/*.test.mjs` — green.
- [ ] App image workflow green, including the blocking Trivy scan on the new image.
- [ ] `az deployment group what-if` on the final bicep — zero unexpected Delete/Modify/Replace lines.
- [ ] Staging smoke test: register → login → re-login after 20 minutes of activity (H-1 fixed) → attempt flow → owner approval → recovery open (no handover) — all pass with the least-privilege DSN.
- [ ] 10 spoofed logins cannot lock out a different credential (H-2 fixed); `/season/notice` floods don't stall ranked traffic (M-1 fixed).
- [ ] `psql` from the public internet to the DB times out (H-4 fixed); GHCR PAT revoked (H-5 fixed).
- [ ] No secrets in tracked files (`git grep` sweep + gitleaks green); no real resource names in tracked docs.
- [ ] Owner has answered the seven questions above and signed the Phase 0 gate.

## Existing defenses to keep (do not "simplify" these away)

1. Parameterized SQL everywhere via `migrate` helpers; `sql.Identifier` for the only dynamic SQL.
2. `correct_belt` never persisted or serialized — answer isolation is a design invariant.
3. Uniform 404s for missing vs. foreign resources — no existence oracles.
4. Timing-parity login (dummy Argon2id verify on every failure path).
5. DB-enforced invariants: single-owner partial unique index, one-active-credential, one-unfinished-attempt, settlement PK + ledger UNIQUE (double-application impossible), one-way answer acceptance trigger.
6. Origin guard fail-closed on writes without Origin/Referer; capability tokens header-only, constant-time compared, checked before any engine side effect.
7. CSP without inline scripts; streaming 64KB body cap; `no-store` on `/api`; docs/OpenAPI disabled by default.
8. SHA-pinned actions, digest-only deploys, non-root image with pip removed, `persist-credentials: false` everywhere.
