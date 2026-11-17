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

One correction to Task 6, Step 2, now applied to its text: the private DNS zone is `privatelink.postgres.database.azure.com`. The plan originally read `privelink`, which resolves to nothing — the app would keep reaching the database over the public internet and look perfectly healthy doing it.

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

- [x] **Step 1: Write the failing regression tests** (through the HTTP layer, against the scratch DB, in the existing test style)

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

- [x] **Step 2: Run them and verify they fail** — `backend/.venv/bin/python -m unittest backend.tests.test_auth_sessions -v` → both FAIL.
- [x] **Step 3: Fix both helpers identically**

```python
with _db_connection() as conn:
    account = get_account_by_session(conn, raw_token)
    conn.commit()  # persist the last_seen_at refresh / idle revocation
```

If `request_deletion` does not commit internally, add the same `conn.commit()` to `delete_account` and extend its test to assert the row landed.

- [x] **Step 4: Sweep the bug class:** `grep -n "_db_connection" backend/ -r` — every `with` block that writes through `migrate.execute` must commit (login `auth.py:144`, logout `:167`, reauth `:250` already do). Fix any others found; one test each.
- [x] **Step 5: Full suites pass** — backend unittest + `node --test tests/*.test.mjs`.
- [x] **Step 6: Commit** — `security: commit session idle-refresh and revocation writes (audit H-1)`

**Done 2026-11-16, PR #150.** The Step 4 sweep found no other instance: every other `_db_connection` site commits itself or calls a helper that commits internally. Verified in the running app as well — `last_seen_at` advances, a session idle for 14 minutes survives and its clock restarts, one idle for 16 minutes is refused with `revoked_at` written.

### Task 2: Rate-limiter hardening — key by client+target, stop resetting on success (H-2, code half) — `TDD`

**Files:**
- Modify: `backend/auth/rate_limit.py:64-67` (`record_success`)
- Modify: `backend/routers/auth.py:124-141` (login), `:232-235` (reauth), `:274-277` (delete) — switch to the new key
- Create: helper `def _login_rate_key(request, login_id: str) -> str` in `backend/auth/rate_limit.py`
- Test: `backend/tests/test_auth_rate_limit.py` (extend)

**Interfaces:**
- Produces: `_login_rate_key(request, login_id) -> str` — `f"{_client_key(request)}|{target}"` where `target` is `derive_lookup_key(login_id)` on valid input, the literal `"invalid"` when `derive_lookup_key` raises `ValueError`. Registration limiter keeps plain `_client_key` (its global 200/day cap is by design).

- [x] **Step 1: Failing tests:**
  1. 10 failures against login ID A from one client → 11th attempt for A gets 429, while a login for ID B from the same client is still allowed.
  2. Interleave 10 failures on A with 10 **successes** on the attacker's own ID → the counter for A is NOT reset; next A attempt gets 429.
  3. Malformed login ID → key falls back to `"invalid"`, no 500.

- [x] **Step 2: Run → FAIL.**
- [x] **Step 3: Implement.** `record_success` zeroes the bucket instead of deleting it (`bucket.failures = 0`); login/reauth/delete use `_login_rate_key`.
- [x] **Step 4: Suite passes (includes the existing X-Forwarded-For trust A/B tests — they must stay green).**
- [x] **Step 5: Commit** — `security: key login limiter by client+credential, expire buckets instead of resetting (audit H-2)`

**Done 2026-11-16, PR #151.** Verified in the running app: ten wrong guesses lock that one login ID out while a real login from the same address still gets in.

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
- [x] **Step 3: Bicep changes** — after the identity bootstrap is approved: attach the dedicated user-assigned runtime identity to the container app and use its resource ID in the registry entry; remove both registry params and the secret entry.
- [x] **Step 4: Bootstrap runtime read access** — after explicit approval of the identity and both scopes, register the ManagedIdentity provider if needed and deploy `runtime-identity.bicep`. Its resource-scoped AcrPull and Key Vault Secrets User assignments reference the new identity principal. Verify the resolved principal and exact direct assignments before later app association. No publisher or subscription-wide role belongs to the runtime.
- [ ] **Step 5: Move the database secret into Key Vault (audit §3 P0-1)** — the dedicated vault already exists. Prepare a separately reviewed operator write path and transfer the limited-role DSN through an in-memory or protected-file method, never a command argument. The identity bootstrap grants read access only; it does not grant an operator secret-write access. Verify its existing vault read binding rather than adding a duplicate. In the app Bicep, replace the inline secret value with the Key Vault URI and runtime identity reference, then remove the `databaseUrl` parameter only after the tested transition/rollback path is ready.
- [x] **Step 6: Verify:** app pulls and boots; `az containerapp show` config contains no registry password and no inline DB secret; GHCR PAT is **revoked**.
- [x] **Step 7: Update tests + runbook; commit** — `security: ACR + managed identity + Key Vault; PAT and inline DB secret retired (audit H-5, §3 P0-1)` — the identity half. The Key Vault half of the message belongs to Step 5, still open.

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

Task 5 image pull applied — 2026-11-17: PRs #172 and #173 merged; #174 carries
a follow-up fix. The app now pulls as itself.

What was done, in order: the digest already running was copied into the
dedicated registry with `az acr import` (one use of the GHCR token, by the
owner, from Cloud Shell), the copy's digest was confirmed to equal
`b60d5a8e…`, the identity's AcrPull on that registry was confirmed present
from the Task 4 bootstrap, and `sort-tester-app-h5` deployed in 1m40.

What-if before deploying showed `2 to modify`, no Delete and no Replace:
`username`/`passwordSecretRef` out and `identity` in, `server` from
`ghcr.io` to `<acr-name>.azurecr.io`, the `registry-password`
secret gone, and the same digest either side. The environment was untouched,
so the address did not change.

Verified after: the one active revision `--0000002` is `RunningAtMaxScale`
pulling from the ACR host, `/health` is 200 and
`/api/ranked/season/notice` is 200 with real JSON, so the app reaches the
private database through the new pull path. The parameters file was shredded.

Three traps, all now in the runbook: `az acr import --image` is a target
**tag** and refuses a digest (`InvalidImportImageParameter`); `az acr
manifest list-metadata` reverses `-r` and `-n`; and `imageRepository` still
defaulted to the GHCR account prefix `renilsonjr/…`, which does not exist
inside our own registry (fixed in #174, worked around by passing the
parameter for this deployment). A fourth, not a trap but worth recording:
only one revision exists, so "roll back to the previous revision" was never
available — the real rollback was a redeploy pointing at GHCR.

Steps 3 and 7 are newly complete. Step 2 is **not**: the publish workflow
still does not push to the registry, so every deployment needs the manual
import. Step 5 (Key Vault for the database secret) is untouched. Step 6
closes with the GHCR token's revocation, which is the finding itself.

Task 5 vault secret applied — 2026-11-17: PR #176. The database URL is in
`kv-sortstg-…` and the app's own configuration holds only its versionless
address plus the identity that may fetch it. Reading the app's configuration
now reveals nothing; seeing the URL needs data access to the vault, which
after this nobody has.

In order: the template compiled (the conditional secret was the risk, and it
was fine); the owner took `Key Vault Secrets Officer` on the vault **by
name**, because the vault uses Azure RBAC where being subscription Owner
grants no data access; the URL was written from a file in one
write-store-shred chain; the identity's `Key Vault Secrets User` from Task 4
was confirmed; `sort-tester-app-vault` succeeded at 07:41; and the write role
was handed back at the end.

Verification, and why the obvious check was not enough: after the deployment
the configuration showed `keyVaultUrl` and `identity` with no `value`, and
both routes answered 200 — but the revision was still `--0000002`. Changing
where a secret comes from creates no new revision, and the secret is
injected at container start, so that process was still running on the old
injected value and its 200s proved nothing about the vault. The revision was
restarted on purpose; `/health` and `/api/ranked/season/notice` were 200
after it. That is the proof. Without the restart a broken vault path would
have stayed hidden until the next scale event.

Also learned: what-if does not render a secure value's **removal**, so the
`value` leaving was never visible in the preview and had to come from
`az containerapp show` afterwards. And this Cloud Shell has no storage
mounted — no `~/clouddrive`, and the home directory with the clone is gone
by the next session — which is what had actually removed §5b's parameters
file. The runbook's advice to write under `~/clouddrive` was wrong and is
corrected.

The password was mistyped again (11 characters against 32) and the printed
length caught it before anything was written. A wrong URL in the vault would
have left an app that cannot start, with nothing in the error naming the
password.

Step 6 is newly complete. Step 5 stays open for its last clause only: the
`databaseUrl` parameter is still in the template, deliberately, since the
rollback it provides has now been proven unnecessary but not yet removed.
Step 2 is also still open — the publish workflow does not push to the
registry, so each deployment needs the manual import.

### Task 6: Network isolation — VNet-injected environment + private endpoint (H-4) — `OPS` *(biggest change: plan a deployment window)*

**Files:**
- Modify: `infra/azure/container-apps-app.bicep` (VNet-injected `appEnvironment`, private endpoint for the DB)
- Create: VNet/subnet + private DNS zone resources (in this template or a sibling `network.bicep`)
- Modify: `container-apps-app.md` (new §5a replacing the 0.0.0.0 rule; teardown §8 updated)

- [x] **Step 1: Owner decisions (blocking):** subnet CIDR for the ACA environment, whether the spike/staging apps retire first (recommended — they're disposable), downtime window (environment recreate).

  **Answered 2026-11-16.** `10.20.0.0/16` for the network, `10.20.1.0/27` for the environment and `10.20.2.0/28` for the endpoint — there is no other virtual network to collide with. The spike and staging apps retire first. The environment is recreated and **the app's address changes**, with 15–30 minutes of downtime accepted: nobody outside the project uses the app yet.
- [x] **Step 2: Create network:** VNet + delegated subnet (`Microsoft.App/environments`), private DNS zone `privatelink.postgres.database.azure.com` linked to the VNet, private endpoint on the Flexible Server targeting its `postgresqlServer` group ID.
- [x] **Step 3: Update the bicep** — `appEnvironment.properties.vnetConfiguration` with the subnet resourceId; the DB URL host stays the server FQDN (resolved privately inside the VNet).
- [x] **Step 4: Redeploy per runbook (parameters via `@file`); what-if clean.**
- [x] **Step 5: Acceptance checks:**
  - App boots, `/health` 200, login + one attempt flow works (DB reachable privately).
  - **Delete the `allow-azure-services` rule** (`az postgres flexible-server firewall-rule delete … --name allow-azure-services`) and confirm the app still works.
  - From outside Azure: `psql` to the server FQDN times out (public access disabled); only the migration firewall rule opens temporarily per runbook §1.
- [x] **Step 6: Commit + runbook** — `security: VNet-injected environment + DB private endpoint, public firewall rule removed (audit H-4)`

**Done 2026-11-16 (PRs #163, #164).** Applied with the owner at the console;
the evidence is in `infra/azure/container-apps-app.md` §5a applied.

Step 5's three acceptance checks all passed: the app boots and reads the
database over the private endpoint, `allow-azure-services` was deleted and the
app kept working, and `psql` from outside the network now times out where it
used to answer.

One deviation to be precise about: that third check is worded "(public access
disabled)", and public access is **not** disabled — it is `Enabled` with zero
firewall rules, which is what refuses every public client today. The owner
chose to stop there because migrations still run often and disabling it makes
each one a two-command dance. Revisit after #84. The runbook carries the note.

Two traps cost a cycle each and are now written into the runbook so the next
person does not pay them again: an environment name reused before the delete
finishes fails with a bare "Operation failed with general exception" and hangs
in `Waiting`; and GHCR needs a **classic** token with `read:packages`, whose
failure only surfaces halfway through the deployment as `DENIED: denied`.

### Task 7: Enforce TLS on every DSN, verify the server certificate (M-4 + audit L1) — `TDD`

**Files:**
- Modify: `backend/db/settings.py:67-81` (`app_database_url`) and `:18-54` (`test_database_url`) — validate effective `sslmode`
- Create: `infra/azure/postgres-ca.pem` (public Azure PostgreSQL root CA — not a secret)
- Modify: `infra/azure/app.Dockerfile` (COPY the PEM to `/app/postgres-ca.pem`), `container-apps-app.md` (DSN gains `sslmode=verify-full&sslrootcert=/app/postgres-ca.pem`)
- Test: `backend/tests/test_db_settings.py` (extend)

**Interfaces:**
- Produces: `app_database_url()` raises `DatabaseConfigError` unless the effective `sslmode` (after libpq defaults) is `verify-full`, `verify-ca`, or `require`; absent `sslmode` is **rejected** (libpq would default to `prefer`). `test_database_url()` applies the same rule **except** when the resolved host is loopback (`127.0.0.1`, `::1`, `localhost`) — local dev Postgres without SSL stays usable. Error messages name the required values.

- [x] **Step 1: Failing tests:** DSN without `sslmode` → `DatabaseConfigError`; `sslmode=disable`/`allow`/`prefer` → rejected; `require`/`verify-full` → accepted (parse with `conninfo_to_dict`, mirroring the existing validation style).
- [x] **Step 2: Run → FAIL. Implement in `settings.py` (both functions).**
- [ ] **Step 3: Bake the CA + update the deploy DSN** as above; `docker build` locally and confirm the file is present (`docker run --rm <img> ls -l /app/postgres-ca.pem`).
- [ ] **Step 4: Redeploy; verify** the app connects (verify-full succeeds only with the right CA) and the DSN validation refuses a tampered `sslmode` at startup.
- [x] **Step 5: Suites pass; commit** — `security: fail closed on DSNs without verified TLS (audit M-4/L1)`

**Phase 0 exit gate (real-data bar):** Tasks 1–7 done; full backend + node suites green; Trivy gate green; `what-if` clean; staging smoke (register/login/attempt/owner flow) passes; owner signs off — only then may the `fictional-only` tag change.

---

## Phase 1 — Pipeline integrity (independent of Phase 0 code tasks)

**Code done 2026-11-16, PR #152; Steps 3 and 4 still open.** The loopback exemption was widened to `app_database_url` as well, because the development server uses the app DSN on `localhost`.

Step 3 took a different route than written: no CA is baked into the image. Azure PostgreSQL chains to a public root, so the runbook points `sslrootcert` at the distro bundle (`/etc/ssl/certs/ca-certificates.crt`) and carries the one-line check to run before deploying. **Still to do:** build the image and confirm that bundle is there, then Step 4 — redeploy with the new DSN and confirm the app connects with `verify-full` against the real server.

### Task 8: Publish environment gate (M-7) — `OPS`

- Modify: `.github/workflows/app-image-publish.yml` — add `environment: publish` to the publish job.
- Repo settings (manual): create environment `publish`, required reviewers = the owner, deployment branch policy = `main` (+ `codex/ranked-mode` while it is the working branch).
- Add a guard step in the job: `if github.ref not in allowed refs → fail fast` (belt-and-braces alongside the environment policy).
- Verify: dispatch from a disallowed branch is rejected; a dispatch from an allowed branch waits for approval; expected reviewers listed in the run.
- Commit — `security: require publish environment approval and branch policy (audit M-7)`

Task 8 applied — 2026-11-17: the `publish` environment exists on the
repository with `renilsonjr` as a required reviewer and custom branch
policies for `main` and `codex/ranked-mode` only. The owner chose to have it
created through the API rather than the settings UI; the created rules were
read back and matched.

Order mattered, and the reason is worth keeping: a workflow naming an
environment that does not exist makes GitHub create an **unprotected** one.
Merging the workflow first would have produced a gate that approves
everything while looking like a gate — worse than no gate, because it
invites trust. So the environment and its rules were created first, and the
workflow second.

The in-file branch check is deliberately redundant beside the environment's
branch policy. The policy is repository configuration: an admin can widen it
in the settings UI, leaving no commit and no diff. The check in the workflow
cannot be widened without a change someone can review. It also runs before
the build and the login, so a refused ref never reaches a registry
credential.

`backend/tests/test_publish_workflow.py` guards the half that lives in the
repository (5 tests). Both were mutation-checked: removing
`environment: publish` fails, and turning the refusal into a warning fails.
The half that lives in GitHub's settings cannot be tested from the
repository, which is what the verification step below is for.

Task 8 verified — 2026-11-17, after PR #178 merged. Both dispatches were run
and nothing was published.

From a branch outside the policy (a throwaway cut from `codex/ranked-mode`,
deleted afterwards), run `44121891487` ended in `failure` with **zero steps
executed** and no job log. The environment's branch policy refuses before
the job starts, so on a disallowed ref nothing runs at all -- not the branch
check, not the build, not the registry login. The in-file check is therefore
a second line and never the first, which is what it was meant to be.

From `codex/ranked-mode`, run `44122057446` went to `waiting`, not
`in_progress`. Its pending deployment named environment `publish`, reviewer
`renilsonjr`, wait timer 0. It was cancelled without approving, so no image
was built or pushed.

Note for whoever repeats this: `workflow_dispatch` reads the workflow from
the ref it is dispatched from, so the change must be merged before the
disallowed-branch test, and that branch must still exist -- GitHub deletes
the PR branch on merge.

Task 8 is complete.

### Task 9: Secret scanning + dependency review + pip-audit (M-8) — `OPS`

- Create: `.github/workflows/security-gates.yml` — on push/PR: gitleaks (action SHA-pinned); on PR: `actions/dependency-review` (SHA-pinned); a `pip-audit` job installing `pip-audit` and running `pip-audit -r backend/requirements-runtime.txt` (dev set too if desired; runtime first).
- Create: `.github/dependabot.yml` — `pip` ecosystem watching `backend/`, plus `github-actions` ecosystem (both update the pinned digests by PR).
- One-time provenance review (blocking question for the owner): the dev-only packages `httpx2`, `httpcore2`, `fastar`, `agent-detector`, `fastapi-cloud-cli` in `backend/requirements.txt` — none ship in the runtime image, but they execute in CI; confirm publisher/provenance or drop them from the dev set.
- Repo settings (manual): enable secret scanning + push protection.
- Verify: workflow runs green on the opening PR; push protection blocks a test commit containing a fake `AKIA…`-style key (try on a scratch branch).
- Commit — `security: secret scanning, dependency review, pip-audit, Dependabot (audit M-8)`

Task 9 provenance answered — 2026-11-17: all five dev-only packages are
genuine, which the names argue against. `httpx2` and `httpcore2` read like
textbook typosquats and are in fact Tom Christie's own successors to httpx,
published under the `pydantic` organisation. `fastar` is Jonathan Ehwald's
bindings to the Rust tar crate. `agent-detector`, `detect-installer` and
`rignore` are Patrick Arminio's, and `fastapi-cloud-cli` is FastAPI Labs'.
Checked against PyPI's own metadata: publisher, summary and source URL.

They arrive transitively: `fastapi[standard]` pulls `fastapi-cli`, which
pulls `fastapi-cloud-cli`, which pulls the rest. None reaches the runtime
image, but they do execute in CI, which is where the publish credentials
live. Owner decision 2026-11-17: keep them and record the check, rather
than installing fastapi without the `standard` extra. The provenance is
sound; the reason to drop them would be surface area, not suspicion.

Task 9 applied — 2026-11-17: `.github/workflows/security-gates.yml` and
`.github/dependabot.yml`.

Secret scanning and push protection were **already enabled** on the
repository, which is public, so nothing had to be turned on. Two related
options are off: `secret_scanning_non_provider_patterns` and
`secret_scanning_validity_checks`. The first is worth a decision of its
own -- the provider patterns catch an AWS or GitHub token, but a
`postgresql://user:password@host` is not a provider token and none of them
match it, which is exactly the shape this project handles by hand.

Three gates, answering three different questions: gitleaks on the history,
dependency review on what a pull request adds, and pip-audit on what is
already installed. The third also runs weekly on a schedule, because a
dependency that was clean when it was added does not stay clean and no
push would ever notice.

Every third-party action is pinned to a commit SHA resolved from its tag
and verified to be a commit, not an annotated tag object. That pinning is
why the `github-actions` Dependabot ecosystem matters as much as `pip`:
nothing else updates those pins, and without it they age into unpatched
versions while looking deliberate.

The runtime audit is `--strict` and may not be made advisory -- a finding
there is a finding in production -- while the dev audit reports without
failing. Both were run locally before opening the pull request, in an
isolated environment, and both reported no known vulnerabilities, so the
gate's first run should be green for reasons other than an empty database.

`backend/tests/test_security_gates_workflow.py` guards the ways a gate can
report success while checking nothing: a tag instead of a SHA, a shallow
checkout that leaves gitleaks no history, `continue-on-error` on the
runtime audit, and permissions wider than read.

First run, and what it exposed — 2026-11-17: all six checks on PR #180
passed, and `gitleaks-action` v3 needed no licence key on this public
personal repository. But the secret scan finished in 8 seconds, and its log
said **"1 commits scanned, ~11974 bytes"**.

So the action scans the commits of the event, never the history. The
`fetch-depth: 0` is necessary -- without it the action cannot resolve its
range at all -- but it is not sufficient, and the gate as first written
would have caught a secret being *added* while never finding one already
in the repository. That is the question that matters after a key leaks.

The guard written for it, `test_the_secret_scan_reads_the_whole_history`,
asserted the fetch depth and the action's presence and passed. It was
named for an outcome it could not check. Renamed to
`test_the_change_scan_has_a_range_to_work_with`, which is what it tests.

Fixed by adding a second job, `secrets-history`, running weekly and on
dispatch: `gitleaks detect` with no `--log-opts`, which scans every commit.
It runs the release binary rather than the action, because the action
derives its range from the event and no event means "everything"; the
binary is pinned by version and checked against the release's published
SHA-256, since a binary fetched at run time is a supply chain of its own.

The first whole-history scan then failed, with four findings — all the
same and all false. The default `generic-api-key` rule reads
the word "token" followed by a named numeric argument as a keyword and its
value; what it found was the idle window in the session-expiry tests.

(That sentence is written around the pattern rather than quoting it. The
first draft quoted the flagged line verbatim and the scanner found it
here, in the plan. Widening the allowlist to cover documentation was the
wrong answer: documentation is exactly where a credential ends up pasted
into an example.)

`.gitleaks.toml` extends the default rules rather than replacing them, and
the exception is tied to one file **and** one shape (`idle_seconds=` with a
bare integer). A path-only allowlist would let a real key pasted into that
same file through; a directory-wide one would blind the scanner where
fixtures live, which is where a key gets pasted "just for a moment".
Guards enforce both: no allowlist path that is not a single `.py` file,
and no exception without a shape.

The log also showed the two secret jobs doing identical work: on a
dispatch the action has no range and scans everything. The per-change job
now steps aside on schedule and dispatch. The explicit history job stays,
because the action's behaviour there is implicit in the event and implicit
behaviour changes without a diff.

Verified — 2026-11-17, run `44125295575`: whole history green, **362
commits, ~7.73 MB, no leaks**. Set against the first run's "1 commit,
~12 KB", that is the measure of what the gate was worth before and is
worth now.

Non-provider patterns are **not available** on this repository — 2026-11-17.
The REST API accepts a PATCH enabling them and reports success, and the
value stays `disabled`; the repository's own security page has no such
toggle. The likeliest reason is that generic-secret detection belongs to
the paid Secret Protection product, while a public repository gets
partner-pattern detection for free. Recorded as observed, not as a billing
claim: what is certain is that the switch is absent and the API's success
response meant nothing.

The gap is narrower than it looks, because gitleaks' `generic-api-key` is
generic-secret detection and runs on every push and pull request here --
that is the rule that produced all of today's findings. What is lost is
*when*: GitHub's push protection refuses the push, while gitleaks reports
after the commit has reached a public repository. For a database URL
committed by accident, those few minutes are the whole difference.

Still not done: the push-protection test with a fake key on a scratch
branch.

### Task 10: Digest-pin CI images, slim the spike image (M-9) — `OPS`

- Modify: `.github/workflows/app-image.yml:199-200` — replace `aquasec/trivy:0.76.2` with `aquasec/trivy@sha256:<digest>` (get it: `docker manifest inspect aquasec/trivy:0.76.2`); same treatment for the `postgres:18-alpine` service image.
- Modify: `infra/azure/spike.Dockerfile:7-10` — build from `backend/requirements-runtime.txt`; delete the `--upgrade setuptools/msgpack` hack.
- Modify: `infra/azure/app.Dockerfile.dockerignore:13-24` — re-ignore `backend/requirements.txt` and `backend/tests/**` so only the runtime manifest and app code ship in the app image (audit L4).
- Verify: spike workflow builds and its `/health` probe passes; Trivy step still gates HIGH/CRITICAL; digest recorded in the workflow file.
- Commit — `security: digest-pinned CI images, spike image on runtime deps only (audit M-9)`

Task 10 applied — 2026-11-17: the two tagged images CI runs are now pinned
by digest, the spike image installs the runtime set, and the development
manifest no longer ships in the app image.

`postgres:18-alpine` → `postgres@sha256:b6972e11…` and
`aquasec/trivy:0.76.2` → `aquasec/trivy@sha256:8f6bb947…`. The two are
worth different amounts. A moved Postgres tag means tests failing with no
commit to explain them, which costs a day. The Trivy container is handed
`/var/run/docker.sock`, so whatever that tag resolves to runs with control
of the daemon that builds and holds our images -- there the tag is the
trust boundary. The version is kept in a comment beside each digest,
because a digest says nothing about which release it is.

Note the limit of this: Dependabot does not update a service image or a
`docker run` argument, so these move only when a person moves them. A
stale pin a human can see is still better than a fresh one nobody chose,
but it is a thing to revisit rather than a thing that maintains itself.

The spike image installed `requirements.txt` -- the whole development
environment -- to serve a single `/health` route, and then carried two
pinned upgrades (`setuptools`, `msgpack`) to patch findings in packages it
never imported. On `requirements-runtime.txt` both upgrades became
unnecessary and were deleted with what needed them.

For the app image (audit L4), `COPY backend` takes the whole directory, so
`backend/requirements.txt` was shipping: a printed list of every package
and version the project uses, handed to anyone who pulls the image. Now
excluded, with the workflow's existing "unexpected paths" check extended
to observe its absence rather than trusting the ignore file.

`backend/tests/test_ci_images.py` guards all of it, including a test that
fails on *any* image named by tag in that workflow, so the next one added
is caught rather than noticed. Mutation-checked: restoring the Postgres
tag fails two guards.

Not verified here: the spike workflow's own build and `/health` probe.
There is no Docker on the machine this was written on, so the image was
not built; the workflow run is the verification.

---

## Phase 2 — Resilience (start after Task 1; Tasks 11–14 are independent of each other)

### Task 11: Public endpoint off the sweep chain (M-1) — `TDD`

**Files:**
- Modify: `backend/routers/ranked.py:55-79` (keep `get_db` as-is for authenticated routes), `:824-825`
- Create in the same file: `def get_readonly_db():` — `with _db_connection() as conn: yield conn` (no sweeps)
- Test: `backend/tests/test_ranked_leaderboard_router.py` or a new `test_season_notice.py`

**Interfaces:**
- Produces: `get_readonly_db` — plain connection dependency for read-only public routes.

- [x] **Step 1: Failing test:** `/api/ranked/season/notice` returns correct data while **no sweep function runs** (monkeypatch `finish_due_seasons`/`close_due_rounds`/`purge_due_cases`/`purge_deleted_accounts` to raise; endpoint must still answer — currently fails because `get_db` calls them).
- [x] **Step 2: Implement:** `season_notice` takes `conn=Depends(get_readonly_db)`.
- [x] **Step 3: Sweeps still run on authenticated routes** — assert one authenticated ranked call invokes the sweep chain (existing tests largely cover this; add one explicit assertion).
- [x] **Step 4 (optional, only if load tests show need):** in-process sweep throttle behind `SORT_TESTER_SWEEP_INTERVAL_SECONDS` (default `0` = current behavior) — never changes semantics, only frequency.
- [x] **Step 5: Suites pass; commit** — `security: read-only dependency for public season notice, sweeps off the anonymous path (audit M-1)`

**Done 2026-11-16, PR #165.** Step 4's optional throttle was not built: the sweeps now run only behind an account, which was the whole finding. Checked in the running app — the notice answers in single-digit milliseconds and a burst of ten concurrent calls all return.

### Task 12: Lock-free early return in `finalize_prizes` (M-2) — `TDD`

**Files:**
- Modify: `backend/ranked/tiebreaks.py:926-935`
- Test: `backend/tests/test_ranked_prize_finalization.py` (extend)

- [x] **Step 1: Failing test:** season already final → second call returns `"final"` **without** any `FOR UPDATE` (monkeypatch/observe: e.g., assert via a second connection holding the row lock that the call still completes — currently blocks/fails).
- [x] **Step 2: Implement:** lock-free `SELECT phase, frozen_at, prizes_final_at, closes_at, closed_at FROM seasons WHERE id = %s` first; return early unless the row is an unfrozen-pending official season; only then re-select `FOR UPDATE` and re-check (double-checked locking — the row can change between reads).
- [x] **Step 3: `test_ranked_races.py` + prize finalization tests pass unchanged (concurrency semantics preserved).**
- [x] **Step 4: Commit** — `security: finalize_prizes checks before locking, not under lock (audit M-2)`

**Done 2026-11-16, PR #167.** `test_ranked_races` stayed green unchanged. A new test holds the season row from another connection and asserts that a season *with work to do* still waits for the lock, so the double-award protection cannot be optimised away later.

### Task 13: Points bounds — no more smallint brick (M-3) — `TDD` + `OPS`

**Files:**
- Modify: `backend/ranked/scoring.py:69-73` (clamp in `settle`)
- Create: `backend/migrations/versions/0035_points_bounds.py`
- Test: `backend/tests/test_ranked_scoring.py` (extend), new schema test in `test_db_balance_ledger_schema.py` style

- [x] **Step 0 (owner decision, blocking):** confirm negative balances are a legitimate game state (wrong answers deduct, so yes per current rules) → bounds are `±30000`, not `>= 0`.
- [x] **Step 1: Failing tests:** `settle(points_before=30000, …quit)` → `points_after == 29990` (stays in range); `settle(points_before=-30000, …quit)` → floor holds; settlement of a clamped result succeeds against a `smallint` column.
- [x] **Step 2: Implement clamp:** after computing `points_after` for partial outcomes, `points_after = max(min(points_after, 30000), -30000)`.
- [x] **Step 3: Migration 0035** (down_revision = `0034`): `ALTER TABLE balances ADD CONSTRAINT balances_points_range CHECK (current_points BETWEEN -30000 AND 30000)`; same for `balance_history.adjustment, points_before, points_after` (bounds wide enough for the clamp: `adjustment BETWEEN -60000 AND 60000`).
- [x] **Step 4: Verify single head:** `backend/.venv/bin/python -c "from backend.db import migrate, settings; print(migrate.current_revision(settings.test_database_url()))"` → `0035`; full suite green.
- [x] **Step 5: Commit** — `security: clamp settled points and add schema bounds (audit M-3)`

**Done 2026-11-16, PR #168, migration applied the same day.**

Step 0's question was already answered by the code: `ranks.badge_for`
documents that a negative total is Iron, so negative balances are a
legitimate state and the bounds are a range, not a floor at zero.

The owner chose to clamp at +/-30000 rather than widen the columns, so the
ceiling is a rule of the game: a Challenger who reaches it stops gaining,
the way a capped badge does. The existing result screen already explains
that, since a clamp and a badge cap produce the same shape -- the overflow
reads "did not fit in Challenger".

The migration is numbered **0036**, not 0035 as the plan wrote: 0035 was
taken by the Ranked question options while this plan sat unapplied.

Applied to staging on 2026-11-16, the first migration since the database
went private: firewall opened for one address, `upgrade_app` ran
0035 -> 0036, the rule was deleted, and the rule list is empty again. The
app answered `/api/ranked/season/notice` afterwards, so it still reads the
database.

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

Task 5 of this task's own list is the deploy; steps 1-3 and 5 are done.

Task 14 applied — 2026-11-17: `backend/db/pool.py`, both routers'
`_db_connection` on it, and `psycopg-pool==3.3.3` pinned in both manifests
(its only dependency, typing_extensions, was already pinned at the same
version).

**Divergence from this plan, owner decision 2026-11-17.** The interface
above specified a checkout that commits on clean exit. It does not.
`psycopg_pool`'s own `pool.connection()` helper does exactly that, which
is why this module borrows and returns by hand instead. The reason is
that committing on exit silently changes what every route means: today a
route that writes and does not commit discards the write, and the H-1 fix
depends on a commit being something a route *does*. A route that relied
on the discard would have started writing with no test failing. The
explicit commits and Task 1's guards stay as they are.

The timeout is part of the DSN rather than a statement after checkout.
Set per connection it is one more thing to forget, and a connection that
skipped it would look identical to one that did not. The test asks the
session what it will enforce instead of checking what was configured.

**A health check on checkout was added, which this plan did not ask for,
and it turned out to be load-bearing.** With it removed, two router tests
fail: the scratch database is recreated between test classes and pooled
connections then point at a database that no longer exists. The same
shape exists in production -- a restarted database, a dropped idle
connection, a blip to the private endpoint -- and without the check the
first request to borrow a dead connection is the one that pays.

Its cost is measured, not estimated: the full suite went from 181s to
389s. That ratio is an artefact of the setting. Each test makes many
requests against a local Postgres where every query is a fraction of a
millisecond, so one extra round trip dominates; against the private
endpoint it is one round trip on a request that already makes several.

Not done: **step 4, the burst verification**. Nothing has been deployed,
and `pg_stat_activity` has not been watched showing <= 8 app connections
under load. Until that runs, the cap is a configured number rather than
an observed one.

### Task 15: Runbook secrets off the CLI + docs hygiene (M-6 + L3) — `OPS`

- Modify: `.gitignore` — add `infra/azure/*.parameters*.json`.
- Modify: `infra/azure/container-apps-app.md:181-185, 227-229` — parameters via `@infra/azure/app.parameters.local.json` (template shown with placeholders; the real file untracked), created with `read -rsp` guidance like §1d.
- Modify: `container-apps-app.md:40` — replace the real server name with a placeholder (keep real names in the private inventory only); update `infra/azure/README.md:10-20` so the app template is listed as the live deployable.
- Verify: `git check-ignore infra/azure/app.parameters.local.json` → matches; `git grep pg-sort-tester` → no matches.
- Commit — `security: no secrets on the CLI, no real resource names in tracked docs (audit M-6/L3)`

Task 15 applied — 2026-11-17.

Real names out of tracked prose: the database server, the registry, the
vault and one principal id, across four documents. Two of the four were
written **today**, in this plan and in the runbook, while recording the
work -- which is the honest shape of this finding. It is not a mistake
made once and found later; it is a thing that happens every time someone
writes down what they just did.

What was not leaked, and is worth knowing: no subscription id, no app
ingress host, no client id, no DSN. The records written today used
truncated names and short digests.

Severity, stated plainly: these are not credentials. On a public
repository they are reconnaissance -- they say which registry, which
vault and which server to probe, and vault and registry names resolve in
global DNS.

Two GUIDs were deliberately **kept**: the AcrPull and Key Vault Secrets
User role definition ids. Those are Microsoft's, identical in every
subscription, and writing a role's id beside its name is how a reader
checks that a template grants what it claims to. The two role *assignment*
ids, which are ours, were replaced.

`.gitignore` now covers parameters files by shape rather than by name, so
a file nobody thought to list is still covered; the failure mode here is
one careless `git add` of a file holding the database password.

`backend/tests/test_docs_hygiene.py` guards both halves. It matches the
*shape* of these names and never the values -- a guard that spelled them
out would be the leak it prevents, exactly as the sentence explaining a
gitleaks false positive became one earlier today. For the ignore rules it
asks `git check-ignore` rather than reading `.gitignore` as text, since
only git's answer is authority on what git would do. Mutation-checked: a
planted vault-shaped name fails it, reported by file and line without
quoting the value.

`infra/azure/README.md` now names `container-apps-app.bicep` as the live
deployable and marks the spike and API-only staging templates as history.
Its standing boundary also said "no PostgreSQL connection from the app
host", which stopped being true when the app template shipped; left
standing it would have read as a rule being broken rather than one
superseded.

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
- [x] `psql` from the public internet to the DB times out (H-4 fixed); GHCR PAT revoked (H-5 fixed).
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
