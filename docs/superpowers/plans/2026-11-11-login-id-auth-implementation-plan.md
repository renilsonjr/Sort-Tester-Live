# Login ID authentication implementation plan

> **Status:** Implemented on `codex/ranked-mode` (2026-11-11). All backend tests and Node regression tests pass. Self-service deletion and owner bootstrap remain as follow-up work.
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement server-side login-ID authentication for employee accounts on top of the existing PostgreSQL identity schema: account creation issues a one-time login ID, login consumes only that ID, sessions are opaque PostgreSQL-backed cookies, and admins can regenerate a lost login ID.

**Architecture:** Add a credentials table and a sessions table via Alembic migrations. Keep generation/hashing/verification in a focused `backend/auth/credentials.py` module and session management in `backend/auth/sessions.py`. Expose a FastAPI router at `backend/routers/auth.py` for register/login/logout/whoami/admin-regenerate. Use `argon2-cffi` for login-ID verifier hashing and `secrets` for token generation. Tests use the existing unittest + scratch-DB harness.

**Tech Stack:** FastAPI 0.162, psycopg 3, Alembic (raw-SQL migrations), `argon2-cffi`, Python `secrets`, `pydantic-settings` for auth config, `fastapi.testclient.TestClient` for tests.

**Spec:** `docs/superpowers/plans/2026-11-11-login-id-auth-plan.md` (approved v2 direction).

## Global Constraints

- No raw login ID is ever persisted; store only a verifier (Argon2id) and a lookup key.
- Login ID is shown **once** at creation; the system cannot display it again.
- No password, no username entry for authentication, no self-service recovery of the secret.
- PostgreSQL only; build on existing `accounts` table (`id` UUID, `username`, `tag`).
- Secrets live only in environment variables / settings; nothing credential-related enters git.
- CORS for auth must not use wildcard origins and must set `allow_credentials=True` only in development with explicit loopback origins.
- All auth endpoints use generic failure responses to prevent account/login-ID enumeration.
- Follow existing project conventions: `unittest`, scratch DB via `SORT_TESTER_TEST_DATABASE_URL`, numeric Alembic revision IDs, raw SQL migrations.

## Review Focus

1. **Login ID guessing / brute force** — rate limiting and high entropy must keep the single-factor credential resistant to online and offline guessing.
2. **Lookup-key collisions** — two login IDs must not accidentally share a lookup key; the verify path must handle rare collisions without leakage.
3. **Session fixation / hijacking** — session tokens must be cryptographically random, rotated on privilege changes, and revoked on logout/recovery/deletion.
4. **Admin recovery abuse** — regenerating a login ID must require admin authorization, revoke old sessions, and issue the new ID exactly once.
5. **Cookie security in development** — `allow_credentials=True` must not accidentally enable credentials on wildcard/public origins.

---

### Task 1: Add auth dependencies and settings

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/auth/settings.py`
- Test: `backend/tests/test_auth_settings.py`

**Interfaces:**
- Consumes: `pydantic-settings` package.
- Produces: `AuthSettings` class exposing `session_secret_bytes` (min 32), `argon2_time_cost`, `argon2_memory_cost`, `argon2_parallelism`, `login_id_group_size`, `login_id_total_groups`, `login_id_alphabet`. Other tasks import `auth_settings()` or `get_auth_settings()` from this module.

> **Owner decision:** no email in this plan. Do not create, reference, or validate email addresses for auth or any other purpose.

- [x] **Step 1: Write the failing test**

```python
def test_auth_settings_loads_from_env():
    settings = AuthSettings()
    assert len(settings.session_secret_bytes) >= 32
    assert settings.argon2_memory_cost >= 65536
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m unittest backend.tests.test_auth_settings -v`
Expected: FAIL with module/class not found.

- [x] **Step 3: Add `argon2-cffi` to `backend/requirements.txt` and implement `backend/auth/settings.py`**

Use `pydantic_settings.BaseSettings`. Default to safe values: `argon2_time_cost=3`, `argon2_memory_cost=65536`, `argon2_parallelism=1`, `login_id_total_groups=4`, `login_id_group_size=4`, alphabet `0123456789ABCDEFGHJKMNPQRSTVWXYZ` (Crockford base32 without I, L, O, U).

- [x] **Step 4: Run test to verify it passes**

Run: `python -m unittest backend.tests.test_auth_settings -v`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add backend/requirements.txt backend/auth/settings.py backend/tests/test_auth_settings.py
git commit -m "chore: add argon2-cffi and auth settings module"
```

---

### Task 2: Login ID generation and verification module

**Files:**
- Create: `backend/auth/credentials.py`
- Test: `backend/tests/test_auth_credentials.py`

**Interfaces:**
- Consumes: `AuthSettings` (Task 1).
- Produces:
  - `generate_login_id(settings: AuthSettings) -> str` — returns grouped string like `ABCD-EFGH-JKLM-NPQR`.
  - `derive_lookup_key(login_id: str) -> str` — deterministic, collision-resistant, fast.
  - `hash_login_id(login_id: str) -> str` — Argon2id encoded hash.
  - `verify_login_id(login_id: str, encoded_hash: str) -> bool` — constant-time verify via argon2.
  - `normalize_login_id(login_id: str) -> str` — uppercase, strip dashes/spaces, reject ambiguous chars.

- [x] **Step 1: Write the failing test**

```python
def test_generate_and_verify_login_id():
    settings = AuthSettings()
    login_id = generate_login_id(settings)
    assert len(login_id.replace("-", "")) == settings.login_id_total_groups * settings.login_id_group_size
    hashed = hash_login_id(login_id)
    assert verify_login_id(login_id, hashed)
    assert not verify_login_id("WRONG-WRONG-WRONG-WRNG", hashed)
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m unittest backend.tests.test_auth_credentials -v`
Expected: FAIL with functions not defined.

- [x] **Step 3: Implement `backend/auth/credentials.py`**

Use `secrets.choice` for generation. Lookup key: SHA-256 of normalized login ID, base64url-encoded first 16 bytes (or full). Hash: `argon2.PasswordHasher` with settings-derived params. Normalize: remove `-` and whitespace, uppercase, map ambiguous characters (`iI lL oO uU`) to canonical forms or reject them if not in alphabet.

- [x] **Step 4: Run test to verify it passes**

Run: `python -m unittest backend.tests.test_auth_credentials -v`
Expected: PASS.

- [x] **Step 5: Add collision-resistance test**

```python
def test_different_login_ids_do_not_collide_on_lookup_key():
    # generate many IDs and assert all lookup keys are unique
```

Run: `python -m unittest backend.tests.test_auth_credentials.TestCredentials.test_different_login_ids_do_not_collide_on_lookup_key -v`
Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add backend/auth/credentials.py backend/tests/test_auth_credentials.py
git commit -m "feat: add login ID generation and Argon2 verification"
```

---

### Task 3: Credential storage migration

**Files:**
- Create: `backend/migrations/versions/0008_login_credentials.py`
- Test: `backend/tests/test_db_login_credentials_schema.py`

**Interfaces:**
- Consumes: existing `accounts` table (`0002_accounts.py`).
- Produces: `login_credentials` table with columns `account_id uuid FK accounts(id) ON DELETE CASCADE PRIMARY KEY`, `lookup_key varchar(...) NOT NULL UNIQUE`, `verifier text NOT NULL`, `created_at timestamptz NOT NULL DEFAULT now()`, `revoked_at timestamptz NULL`.

- [x] **Step 1: Write the failing test**

```python
def test_login_credentials_table_exists():
    # after upgrade_to_head, assert table exists and has expected columns/constraints
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m unittest backend.tests.test_db_login_credentials_schema -v`
Expected: FAIL with table not found.

- [x] **Step 3: Write migration `0008_login_credentials.py`**

Follow existing migration style (revision `0008`, down_revision `0007`). Use `op.execute` with raw SQL. Include `CREATE INDEX` on `lookup_key`. Ensure downgrade drops table/index.

- [x] **Step 4: Run test to verify it passes**

Run: `python -m unittest backend.tests.test_db_login_credentials_schema -v`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add backend/migrations/versions/0008_login_credentials.py backend/tests/test_db_login_credentials_schema.py
git commit -m "feat: add login_credentials migration and schema tests"
```

---

### Task 4: Session storage migration

**Files:**
- Create: `backend/migrations/versions/0009_sessions.py`
- Test: `backend/tests/test_db_sessions_schema.py`

**Interfaces:**
- Consumes: `accounts` and `login_credentials` tables.
- Produces: `sessions` table with `id uuid PRIMARY KEY DEFAULT gen_random_uuid()`, `account_id uuid FK accounts(id) ON DELETE CASCADE`, `token_hash bytea NOT NULL UNIQUE`, `created_at timestamptz NOT NULL DEFAULT now()`, `expires_at timestamptz NOT NULL`, `last_seen_at timestamptz NOT NULL DEFAULT now()`, `revoked_at timestamptz NULL`, `ip_address inet NULL`, `user_agent text NULL`.

- [x] **Step 1: Write the failing test**

```python
def test_sessions_table_exists():
    # assert table/columns/constraints after upgrade_to_head
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m unittest backend.tests.test_db_sessions_schema -v`
Expected: FAIL.

- [x] **Step 3: Write migration `0009_sessions.py`**

Follow numeric revision style, down_revision `0008`. Add `CREATE INDEX` on `account_id` and `token_hash`.

- [x] **Step 4: Run test to verify it passes**

Run: `python -m unittest backend.tests.test_db_sessions_schema -v`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add backend/migrations/versions/0009_sessions.py backend/tests/test_db_sessions_schema.py
git commit -m "feat: add sessions migration and schema tests"
```

---

### Task 5: Session manager module

**Files:**
- Create: `backend/auth/sessions.py`
- Test: `backend/tests/test_auth_sessions.py`

**Interfaces:**
- Consumes: `AuthSettings` (Task 1), `psycopg` connection, `sessions` table (Task 4).
- Produces:
  - `create_session(conn, account_id: UUID, ttl_seconds: int, ip: str | None, user_agent: str | None) -> tuple[str, UUID]` — returns `(raw_token, session_id)`.
  - `authenticate_session(conn, raw_token: str) -> dict | None` — returns session row dict including account_id, or None.
  - `revoke_session(conn, session_id: UUID) -> None`.
  - `revoke_all_account_sessions(conn, account_id: UUID) -> None`.

- [x] **Step 1: Write the failing test**

```python
def test_create_and_authenticate_session():
    # create session, then authenticate with raw token, then revoke and fail
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m unittest backend.tests.test_auth_sessions -v`
Expected: FAIL.

- [x] **Step 3: Implement `backend/auth/sessions.py`**

Generate 32-byte token from `secrets.token_urlsafe(32)` or `secrets.token_hex(32)`. Store SHA-256 of token. On authenticate, hash submitted token and look up by `token_hash`, checking `expires_at` and `revoked_at`. Update `last_seen_at` on successful auth.

- [x] **Step 4: Run test to verify it passes**

Run: `python -m unittest backend.tests.test_auth_sessions -v`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add backend/auth/sessions.py backend/tests/test_auth_sessions.py
git commit -m "feat: add opaque server-side session manager"
```

---

### Task 6: Auth service / repository layer

**Files:**
- Create: `backend/auth/service.py`
- Test: `backend/tests/test_auth_service.py`

**Interfaces:**
- Consumes: `credentials` module (Task 2), `sessions` module (Task 5), `login_credentials` and `accounts` tables.
- Produces:
  - `register_account(conn, username: str) -> tuple[UUID, str]` — creates `accounts` row + login_credentials row, returns `(account_id, login_id_shown_once)`.
  - `login_with_id(conn, login_id: str, ttl_seconds: int, ip, user_agent) -> tuple[str, UUID] | None` — verify credential, create session, return token+session_id or None.
  - `admin_regenerate_login_id(conn, admin_account_id: UUID, target_account_id: UUID) -> str | None` — authorize admin, revoke old credential + all sessions, create new login ID, return it once.
  - `get_account_by_session(conn, raw_token: str) -> dict | None`.

- [x] **Step 1: Write the failing test**

```python
def test_register_and_login_round_trip():
    # register -> receive login_id -> login -> receive session token -> get_account_by_session matches
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m unittest backend.tests.test_auth_service -v`
Expected: FAIL.

- [x] **Step 3: Implement `backend/auth/service.py`**

Use existing `accounts` insert rules (username format, tag generation not in scope here — generate a deterministic tag for tests or reuse existing tag logic if present). Store lookup key + verifier. Admin authorization: for now, check that `admin_account_id` belongs to an account with `is_owner` flag (to be bootstrapped separately) or accept a local operator command; document this as a placeholder pending owner bootstrap.

- [x] **Step 4: Run test to verify it passes**

Run: `python -m unittest backend.tests.test_auth_service -v`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add backend/auth/service.py backend/tests/test_auth_service.py
git commit -m "feat: add auth service for register/login/admin regenerate"
```

---

### Task 7: Auth API router

**Files:**
- Create: `backend/routers/auth.py`
- Modify: `backend/main.py` to include router and adjust CORS for credentials
- Test: `backend/tests/test_auth_router.py`

**Interfaces:**
- Consumes: `AuthSettings`, `auth.service` (Task 6), DB connection management.
- Produces: FastAPI routes:
  - `POST /api/auth/register` — request `{ "username": "..." }`, response `{ "account_id": "...", "login_id": "..." }` (shown once).
  - `POST /api/auth/login` — request `{ "login_id": "..." }`, sets `sort_tester_session` cookie, response `{ "account_id": "...", "username": "...", "tag": "..." }`.
  - `POST /api/auth/logout` — revokes session cookie.
  - `GET /api/auth/me` — returns current account info from cookie.
  - `POST /api/auth/admin/regenerate` — admin-only, request `{ "account_id": "..." }`, response `{ "login_id": "..." }`.

- [x] **Step 1: Write the failing test**

```python
def test_register_endpoint_returns_login_id_once():
    # POST /api/auth/register -> 200 and login_id present
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m unittest backend.tests.test_auth_router -v`
Expected: FAIL.

- [x] **Step 3: Implement `backend/routers/auth.py` and wire into `backend/main.py`**

Use dependency to get DB connection. For now, use direct psycopg connection from settings or a connection pool (decide based on existing patterns; `backend/db/migrate.py` has `connect`). CORS: when `SORT_TEST_DEV_ORIGINS` is set, allow `POST` and `Content-Type` header and `allow_credentials=True` for dev only. Production same-origin config is environment-driven.

- [x] **Step 4: Run test to verify it passes**

Run: `python -m unittest backend.tests.test_auth_router -v`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add backend/routers/auth.py backend/main.py backend/tests/test_auth_router.py
git commit -m "feat: add auth API router with register/login/logout/admin regenerate"
```

---

### Task 8: Rate limiting and enumeration resistance

**Files:**
- Create: `backend/auth/rate_limit.py`
- Modify: `backend/routers/auth.py`
- Test: `backend/tests/test_auth_rate_limit.py`

**Interfaces:**
- Consumes: in-memory or PostgreSQL-backed attempt counters.
- Produces: `check_login_attempt(conn, key: str) -> bool` and `record_login_attempt(conn, key: str) -> None` keyed by source IP + target lookup key or just source IP for simplicity.

- [x] **Step 1: Write the failing test**

```python
def test_login_rate_limit_blocks_after_threshold():
    # repeated failed logins from same IP eventually return 429
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m unittest backend.tests.test_auth_rate_limit -v`
Expected: FAIL.

- [x] **Step 3: Implement in-memory rate limiter**

Use a simple dict with timestamp tracking in process memory for v1 (acceptable for single-instance pilot; document that distributed deployment needs Redis). Apply to `/api/auth/login` only. Return generic 401/429 responses.

- [x] **Step 4: Run test to verify it passes**

Run: `python -m unittest backend.tests.test_auth_rate_limit -v`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add backend/auth/rate_limit.py backend/routers/auth.py backend/tests/test_auth_rate_limit.py
git commit -m "feat: add login rate limiting and generic failure responses"
```

---

### Task 9: Frontend login and registration screens (minimal)

**Files:**
- Modify: `index.html` and `src/app.js` (or create `src/auth.js`)
- Test: existing browser tests / manual check; no new backend tests.

**Interfaces:**
- Consumes: `/api/auth/*` endpoints.
- Produces: UI flow for login (single input), register (display login ID once with copy warning), and logout.

- [x] **Step 1: Sketch UI structure**

Add a login modal/screen with one input for login ID and a submit button. Add a register flow that calls `/api/auth/register` and shows the returned `login_id` prominently with a “I saved it” checkbox before continuing.

- [x] **Step 2: Implement minimal frontend changes**

Use vanilla JS matching existing app style. Store only session cookie (HttpOnly, handled by browser); do not store login ID or session token in localStorage.

- [x] **Step 3: Manual verification**

Run static server + backend locally, verify register -> copy login ID -> login -> logout round trip.

- [x] **Step 4: Commit**

```bash
git add index.html src/app.js src/auth.js
git commit -m "feat: minimal login/register/logout frontend"
```

---

### Task 10: Full regression and documentation close-out

**Files:**
- Modify: relevant docs as needed.
- Test: full backend test suite.

- [x] **Step 1: Run full backend test suite**

Run: `python -m unittest discover -s backend/tests -v`
Expected: all pass.

- [x] **Step 2: Run existing Node/browser regression**

Run: `node --test tests/security.test.mjs tests/health-client.test.mjs`
Expected: pass (or update if frontend changes affect tests).

- [x] **Step 3: Update GitHub issue #7**

Edit issue body to reflect login-ID auth acceptance checks and close/comment as appropriate.

- [x] **Step 4: Commit any final doc/comment updates**

```bash
git commit -m "docs: close out login-id auth implementation notes"
```

---

## Self-review

1. **Spec coverage:** v2 plan requirements covered — login ID shown once, no password, admin regeneration, server-side sessions, PostgreSQL, deletion reauth placeholder (actual deletion flow remains in later issues).
2. **Step scan:** each step names one function/file/test with a checkable result.
3. **Type consistency:** `account_id` and `session_id` are UUIDs throughout; login ID is `str`; token is `str` in API, `bytea` hash in DB.
4. **Review Focus:** each item (guessing, collisions, fixation, admin abuse, dev cookie security) is addressed by a task or test.
5. **Proportion:** plan is longer than code will be, but each task is a independently testable increment appropriate for an implementer unfamiliar with the codebase.

## Notes / open calls for the owner

- **Login ID format:** plan proposes 4 groups of 4 Crockford base32 chars = 64 bits of display entropy plus grouping; confirmed by owner.
- **Admin authorization:** plan assumes a placeholder `is_owner` flag for admin regenerate; confirmed by owner.
- **Email:** removed from this plan entirely per owner decision.
- **MFA:** not implemented per owner decision.
