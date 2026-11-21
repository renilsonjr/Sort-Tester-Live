# Managed-identity PostgreSQL authentication — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the hosted app authenticate to PostgreSQL with a short-lived Entra token instead of a password, behind an off-by-default flag, so no code change alters the running app until a separately-approved deployment.

**Architecture:** A `SORT_TESTER_DB_AUTH` flag selects `password` (today's path, default) or `managed_identity`. In managed-identity mode the pool supplies a fresh Entra token as the connection password for each physical connection it opens, via `psycopg_pool`'s per-connection callable `kwargs`; the token comes from an IMDS call (standard library) with a small expiry-aware cache for reuse and refresh. Token/connect failure surfaces as a clean HTTP 503 through one FastAPI exception handler, with no secret logged.

**Tech Stack:** Python 3.14, FastAPI, psycopg 3.3.8, psycopg-pool 3.3.3, Azure IMDS via stdlib `urllib`. Tests: `unittest` (`backend.ci_tests` / `backend/tests`).

**Spec:** `docs/superpowers/specs/2026-11-18-managed-identity-postgres-design.md`.

## Global Constraints

- **No deployment, no Azure change.** This plan ships code, tests and a written (not applied) runbook only. No Bicep edit, no grant change, no `passwordAuth` change, no removal of the vault password reference.
- **`password` is the default mode.** Merging this must change nothing about the running app or local development. No new env var is required in `password` mode.
- **The token value is never logged**, in success, failure or error paths.
- **No new dependency.** The token is fetched from IMDS with the standard library; the container's tested invariants (`test_runtime_requirements`: no `requests`, ≤30 pins) stay intact. (The azure-identity SDK was rejected on 2026-11-18 for breaking both.)
- **Preserve the pool contract:** `MAX_SIZE = 8`, `STATEMENT_TIMEOUT_MS = 5000` in the DSN options, `check=ConnectionPool.check_connection`, `row_factory=dict_row`, explicit transactions (`checkout()` never commits; rolls back on return).
- **TLS unchanged:** both modes pass through `_require_verified_tls`; `managed_identity` DSNs carry no password.
- **Migrations/tests bypass the pool** via `migrate.connect` — do not route them through the token path.
- Confirmed mechanism (psycopg_pool 3.3.3, verified in the repo venv): `KwargsParam = Union[dict, Callable[[], dict]]`; `ConnectionPool._connect` calls `_resolve_kwargs()` on every physical connect, then `connection_class.connect(conninfo, **kwargs)`. A callable `kwargs` is therefore resolved per connection.

---

### Task 1: Mode selector in settings

**Files:**
- Modify: `backend/db/settings.py`
- Test: `backend/tests/test_db_settings.py` (create if absent; otherwise add to the existing settings test module)

**Interfaces:**
- Produces: `settings.DB_AUTH_ENV_VAR = "SORT_TESTER_DB_AUTH"`; `settings.DB_IDENTITY_CLIENT_ID_ENV_VAR = "SORT_TESTER_DB_IDENTITY_CLIENT_ID"`; `settings.db_auth_mode() -> str` returning `"password"` or `"managed_identity"`; raises `DatabaseConfigError` on any other value. `settings.PASSWORD_MODE = "password"`, `settings.MANAGED_IDENTITY_MODE = "managed_identity"`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_db_settings.py
import os
import unittest
from contextlib import contextmanager

from backend.db import settings


@contextmanager
def _env(**values):
    saved = {k: os.environ.get(k) for k in values}
    try:
        for k, v in values.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class DbAuthModeTests(unittest.TestCase):
    def test_defaults_to_password_when_unset(self):
        with _env(SORT_TESTER_DB_AUTH=None):
            self.assertEqual(settings.db_auth_mode(), settings.PASSWORD_MODE)

    def test_blank_is_password(self):
        with _env(SORT_TESTER_DB_AUTH="   "):
            self.assertEqual(settings.db_auth_mode(), settings.PASSWORD_MODE)

    def test_managed_identity_is_accepted(self):
        with _env(SORT_TESTER_DB_AUTH="managed_identity"):
            self.assertEqual(settings.db_auth_mode(), settings.MANAGED_IDENTITY_MODE)

    def test_unknown_mode_raises(self):
        with _env(SORT_TESTER_DB_AUTH="kerberos"):
            with self.assertRaises(settings.DatabaseConfigError):
                settings.db_auth_mode()
```

- [ ] **Step 2: Run to verify it fails**

Run: `backend/.venv/bin/python -m unittest backend.tests.test_db_settings -v`
Expected: FAIL — `AttributeError: module 'backend.db.settings' has no attribute 'db_auth_mode'`.

- [ ] **Step 3: Implement the selector**

Add near the top of `backend/db/settings.py` (after the existing env-var constants):

```python
DB_AUTH_ENV_VAR = "SORT_TESTER_DB_AUTH"
DB_IDENTITY_CLIENT_ID_ENV_VAR = "SORT_TESTER_DB_IDENTITY_CLIENT_ID"
PASSWORD_MODE = "password"
MANAGED_IDENTITY_MODE = "managed_identity"
_DB_AUTH_MODES = (PASSWORD_MODE, MANAGED_IDENTITY_MODE)


def db_auth_mode() -> str:
    """Which runtime authentication mode the app uses.

    Defaults to password so dev and CI need no new variable. An unknown
    value stops startup rather than guessing.
    """
    raw = os.environ.get(DB_AUTH_ENV_VAR, "").strip()
    if not raw:
        return PASSWORD_MODE
    if raw not in _DB_AUTH_MODES:
        raise DatabaseConfigError(
            f"{DB_AUTH_ENV_VAR} must be one of {', '.join(_DB_AUTH_MODES)}; "
            f"got {raw!r}."
        )
    return raw
```

- [ ] **Step 4: Run to verify it passes**

Run: `backend/.venv/bin/python -m unittest backend.tests.test_db_settings -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/db/settings.py backend/tests/test_db_settings.py
git commit -m "feat: SORT_TESTER_DB_AUTH mode selector, password default (#84)"
```

---

### Task 2: Entra token provider (IMDS, stdlib only)

**Files:**
- Create: `backend/db/entra_token.py`
- Create test: `backend/tests/test_entra_token.py`

No dependency change: the IMDS call uses the standard library, so the
container's tested invariants (no `requests`, ≤30 pins) stay intact. (The
azure-identity SDK was rejected on 2026-11-18 because it pulls `requests`
and ~13 transitive packages, breaking `test_runtime_requirements`.)

**Interfaces:**
- Produces: `entra_token.DB_TOKEN_RESOURCE = "https://ossrdbms-aad.database.windows.net"`; `entra_token.db_access_token() -> str`; `entra_token.set_token_fetcher(fn_or_none)` test seam, where `fn() -> dict` returns the parsed IMDS payload (`{"access_token": str, "expires_on": "epoch-seconds"}`); `entra_token.reset_cache()` for tests; `entra_token.TokenUnavailable(Exception)` raised when acquisition fails; `entra_token.EXPIRY_SKEW_SECONDS = 300`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_entra_token.py
import logging
import time
import unittest

from backend.db import entra_token


def _payload(token, ttl_seconds):
    return {"access_token": token, "expires_on": str(int(time.time()) + ttl_seconds)}


class EntraTokenTests(unittest.TestCase):
    def tearDown(self):
        entra_token.set_token_fetcher(None)
        entra_token.reset_cache()

    def test_returns_the_access_token(self):
        entra_token.set_token_fetcher(lambda: _payload("tok-abc", 3600))
        self.assertEqual(entra_token.db_access_token(), "tok-abc")

    def test_reuses_within_lifetime(self):
        calls = {"n": 0}

        def fetch():
            calls["n"] += 1
            return _payload(f"tok-{calls['n']}", 3600)

        entra_token.set_token_fetcher(fetch)
        first = entra_token.db_access_token()
        second = entra_token.db_access_token()
        self.assertEqual(first, "tok-1")
        self.assertEqual(second, "tok-1")
        self.assertEqual(calls["n"], 1, "a valid cached token must be reused")

    def test_refreshes_within_the_skew_window(self):
        calls = {"n": 0}

        def fetch():
            calls["n"] += 1
            # first token already inside the skew window, so it must refetch
            ttl = entra_token.EXPIRY_SKEW_SECONDS - 10 if calls["n"] == 1 else 3600
            return _payload(f"tok-{calls['n']}", ttl)

        entra_token.set_token_fetcher(fetch)
        self.assertEqual(entra_token.db_access_token(), "tok-1")
        self.assertEqual(entra_token.db_access_token(), "tok-2")
        self.assertEqual(calls["n"], 2)

    def test_failure_raises_tokenunavailable(self):
        def fetch():
            raise RuntimeError("imds down")

        entra_token.set_token_fetcher(fetch)
        with self.assertRaises(entra_token.TokenUnavailable):
            entra_token.db_access_token()

    def test_token_value_is_never_logged(self):
        entra_token.set_token_fetcher(lambda: _payload("super-secret-token", 3600))
        with self.assertLogs("backend.db.entra_token", level=logging.DEBUG) as captured:
            logging.getLogger("backend.db.entra_token").debug("probe")
            entra_token.db_access_token()
        self.assertFalse(
            any("super-secret-token" in line for line in captured.output),
            "the token value must never appear in logs",
        )

    def test_failure_logs_the_error_type_not_a_token(self):
        def fetch():
            raise RuntimeError("secret-looking-detail")

        entra_token.set_token_fetcher(fetch)
        with self.assertLogs("backend.db.entra_token", level=logging.DEBUG) as captured:
            try:
                entra_token.db_access_token()
            except entra_token.TokenUnavailable:
                pass
        joined = "\n".join(captured.output)
        self.assertIn("RuntimeError", joined)
        self.assertNotIn("secret-looking-detail", joined)
```

- [ ] **Step 2: Run to verify it fails**

Run: `backend/.venv/bin/python -m unittest backend.tests.test_entra_token -v`
Expected: FAIL — module `backend.db.entra_token` does not exist.

- [ ] **Step 3: Implement the provider**

```python
# backend/db/entra_token.py
"""An Entra access token used as the PostgreSQL connection password (#84).

Managed-identity mode replaces the database password with a short-lived
Entra token fetched from the Azure Instance Metadata Service (IMDS). The
azure-identity SDK would do this, but it pulls requests and a dozen
transitive packages, which breaks the container's tested dependency
invariants (test_runtime_requirements). IMDS is one documented endpoint, so
this calls it with the standard library and caches the token until it is
near expiry. The token value is never logged.
"""
import json
import logging
import os
import time
import urllib.request

from backend.db import settings

logger = logging.getLogger(__name__)

DB_TOKEN_RESOURCE = "https://ossrdbms-aad.database.windows.net"
_IMDS_URL = "http://169.254.169.254/metadata/identity/oauth2/token"
_IMDS_API_VERSION = "2018-02-01"
EXPIRY_SKEW_SECONDS = 300
_IMDS_TIMEOUT_SECONDS = 5

_fetcher = None  # None -> real IMDS call; tests inject a fake with set_token_fetcher
_cache = None  # (token, expires_at) or None


class TokenUnavailable(Exception):
    """Raised when no Entra token could be obtained."""


def set_token_fetcher(fetcher) -> None:
    """Inject a payload fetcher (tests) or reset to the real IMDS call with None."""
    global _fetcher
    _fetcher = fetcher


def reset_cache() -> None:
    """Forget any cached token. For tests and for a deliberate refresh."""
    global _cache
    _cache = None


def _imds_fetch() -> dict:
    client_id = os.environ.get(settings.DB_IDENTITY_CLIENT_ID_ENV_VAR, "").strip()
    if not client_id:
        raise TokenUnavailable(
            f"{settings.DB_IDENTITY_CLIENT_ID_ENV_VAR} is not set; "
            "managed-identity mode needs the user-assigned identity's client id."
        )
    query = urllib.parse.urlencode(
        {
            "api-version": _IMDS_API_VERSION,
            "resource": DB_TOKEN_RESOURCE,
            "client_id": client_id,
        }
    )
    request = urllib.request.Request(
        f"{_IMDS_URL}?{query}", headers={"Metadata": "true"}
    )
    with urllib.request.urlopen(request, timeout=_IMDS_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def db_access_token() -> str:
    """Return a valid Entra token for the PostgreSQL resource.

    Reuses a cached token until it is within EXPIRY_SKEW_SECONDS of expiry,
    then refetches. Never logs the token. On any failure raises
    TokenUnavailable with no token material in the message.
    """
    global _cache
    now = time.time()
    if _cache is not None and now < _cache[1] - EXPIRY_SKEW_SECONDS:
        return _cache[0]
    try:
        payload = (_fetcher or _imds_fetch)()
        token = payload["access_token"]
        expires_at = float(payload["expires_on"])
    except TokenUnavailable:
        raise
    except Exception as error:  # noqa: BLE001 - broad on purpose; no token in the message
        logger.warning("Entra token acquisition failed: %s", type(error).__name__)
        raise TokenUnavailable("could not obtain an Entra token for the database") from error
    _cache = (token, expires_at)
    return token
```

Note: `urllib.parse` must be imported for `urlencode`; add `import urllib.parse` beside `import urllib.request`.

- [ ] **Step 4: Run to verify it passes**

Run: `backend/.venv/bin/python -m unittest backend.tests.test_entra_token -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/db/entra_token.py backend/tests/test_entra_token.py
git commit -m "feat: Entra token from IMDS, cached and never logged (#84)"
```

---

### Task 3: Pool builds the token path

**Files:**
- Modify: `backend/db/pool.py`
- Modify: `backend/routers/auth.py:28-39` (the `_db_connection` / `init_pool` call)
- Modify: `backend/routers/ranked.py:55-64` (the `_db_connection` / `init_pool` call)
- Test: `backend/tests/test_pool_managed_identity.py` (create)

**Interfaces:**
- Consumes: `settings.db_auth_mode()`, `settings.MANAGED_IDENTITY_MODE`, `entra_token.db_access_token`.
- Produces: `pool.init_pool(conninfo: str, *, auth_mode: str = settings.PASSWORD_MODE, token_provider=entra_token.db_access_token) -> None`. In managed-identity mode the pool is built with a callable `kwargs` returning `{"row_factory": dict_row, "password": token_provider()}`; in password mode `kwargs` stays the static `{"row_factory": dict_row}`. No other pool parameter changes.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_pool_managed_identity.py
import unittest
from unittest import mock

from backend.db import pool, settings


class ManagedIdentityPoolTests(unittest.TestCase):
    def tearDown(self):
        pool.close_pool()

    def test_managed_identity_builds_a_callable_kwargs_that_injects_the_token(self):
        calls = {"n": 0}

        def provider():
            calls["n"] += 1
            return f"token-{calls['n']}"

        with mock.patch("backend.db.pool.ConnectionPool") as FakePool:
            FakePool.return_value = mock.MagicMock()
            pool.init_pool(
                "postgresql://app@host/db?sslmode=verify-full",
                auth_mode=settings.MANAGED_IDENTITY_MODE,
                token_provider=provider,
            )
            built_kwargs = FakePool.call_args.kwargs["kwargs"]

        self.assertTrue(callable(built_kwargs), "managed-identity kwargs must be a callable")
        first = built_kwargs()
        second = built_kwargs()
        self.assertEqual(first["password"], "token-1")
        self.assertEqual(second["password"], "token-2")
        self.assertIn("row_factory", first)

    def test_password_mode_keeps_static_kwargs(self):
        with mock.patch("backend.db.pool.ConnectionPool") as FakePool:
            FakePool.return_value = mock.MagicMock()
            pool.init_pool(
                "postgresql://app:pw@host/db?sslmode=verify-full",
                auth_mode=settings.PASSWORD_MODE,
            )
            built_kwargs = FakePool.call_args.kwargs["kwargs"]
        self.assertFalse(callable(built_kwargs))
        self.assertNotIn("password", built_kwargs)
```

- [ ] **Step 2: Run to verify it fails**

Run: `backend/.venv/bin/python -m unittest backend.tests.test_pool_managed_identity -v`
Expected: FAIL — `init_pool()` got an unexpected keyword argument `auth_mode`.

- [ ] **Step 3: Implement in `pool.py`**

Add the imports at the top:

```python
from backend.db import entra_token, settings as db_settings
```

Replace `init_pool` with:

```python
def init_pool(
    conninfo: str,
    *,
    auth_mode: str = db_settings.PASSWORD_MODE,
    token_provider=entra_token.db_access_token,
) -> None:
    """Build the pool if there is not one already.

    Idempotent on purpose: called at startup and defensively from
    `checkout`. In managed-identity mode the connection password is a fresh
    Entra token resolved per physical connection via a callable kwargs; the
    conninfo carries no password. Password mode is unchanged.
    """
    global _pool
    if _pool is not None:
        return
    if auth_mode == db_settings.MANAGED_IDENTITY_MODE:
        def _kwargs():
            return {"row_factory": dict_row, "password": token_provider()}
        pool_kwargs = _kwargs
    else:
        pool_kwargs = {"row_factory": dict_row}
    _pool = ConnectionPool(
        conninfo=_conninfo_with_timeout(conninfo),
        min_size=1,
        max_size=MAX_SIZE,
        kwargs=pool_kwargs,
        check=ConnectionPool.check_connection,
        open=True,
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `backend/.venv/bin/python -m unittest backend.tests.test_pool_managed_identity -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Wire both routers to pass the mode**

In `backend/routers/auth.py`, change the `init_pool` call inside `_db_connection`:

```python
    pool.init_pool(settings.app_database_url(), auth_mode=settings.db_auth_mode())
```

Make the identical change in `backend/routers/ranked.py`'s `_db_connection`.

- [ ] **Step 6: Run the full backend suite**

Run: `backend/.venv/bin/python -m backend.ci_tests`
Expected: all green, 0 skips (password mode unchanged; the new tests pass with mocked pools).

- [ ] **Step 7: Commit**

```bash
git add backend/db/pool.py backend/routers/auth.py backend/routers/ranked.py backend/tests/test_pool_managed_identity.py
git commit -m "feat: pool injects a per-connection Entra token in managed-identity mode (#84)"
```

---

### Task 4: Token/connection failure returns a clean 503

**Files:**
- Modify: `backend/main.py:32-41` (register an exception handler inside `create_app`)
- Test: `backend/tests/test_db_unavailable_503.py` (create)

**Interfaces:**
- Consumes: `entra_token.TokenUnavailable`, `psycopg_pool.PoolTimeout`.
- Produces: a FastAPI exception handler mapping those two exception types to HTTP 503 with body `{"detail": "database temporarily unavailable"}` and no token/DSN in the response or log. Serves every route; the routers are unchanged.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_db_unavailable_503.py
import unittest
from unittest import mock

from fastapi.testclient import TestClient
from psycopg_pool import PoolTimeout

from backend.db import entra_token
from backend.main import create_app


class DbUnavailable503Tests(unittest.TestCase):
    def _client(self):
        return TestClient(create_app(), raise_server_exceptions=False)

    def test_pool_timeout_becomes_503(self):
        with mock.patch("backend.routers.ranked.pool.checkout", side_effect=PoolTimeout("no conn")):
            response = self._client().get("/api/ranked/season/notice")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "database temporarily unavailable")

    def test_token_unavailable_becomes_503_without_secret(self):
        err = entra_token.TokenUnavailable("could not obtain an Entra token for the database")
        with mock.patch("backend.routers.ranked.pool.checkout", side_effect=err):
            response = self._client().get("/api/ranked/season/notice")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("token", response.text.lower())
```

(If `/api/ranked/season/notice` is not the public read path, use the route confirmed in `backend/routers/ranked.py`; it is `get_readonly_db`-backed and needs no auth.)

- [ ] **Step 2: Run to verify it fails**

Run: `backend/.venv/bin/python -m unittest backend.tests.test_db_unavailable_503 -v`
Expected: FAIL — the exception surfaces as 500, not 503.

- [ ] **Step 3: Implement the handler in `create_app`**

Add imports to `backend/main.py`:

```python
from fastapi import Request, status
from fastapi.responses import JSONResponse
from psycopg_pool import PoolTimeout

from backend.db.entra_token import TokenUnavailable
```

Inside `create_app`, after the routers are included:

```python
    @application.exception_handler(TokenUnavailable)
    @application.exception_handler(PoolTimeout)
    def _database_unavailable(_request: Request, _exc: Exception) -> JSONResponse:
        # No token or DSN is read from the exception, so nothing secret can
        # reach the client or the log. A request that needs a *new*
        # connection while none can be made gets this; healthy pooled
        # connections keep serving.
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "database temporarily unavailable"},
        )
```

- [ ] **Step 4: Run to verify it passes**

Run: `backend/.venv/bin/python -m unittest backend.tests.test_db_unavailable_503 -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Run the full suite**

Run: `backend/.venv/bin/python -m backend.ci_tests`
Expected: all green, 0 skips.

- [ ] **Step 6: Commit**

```bash
git add backend/main.py backend/tests/test_db_unavailable_503.py
git commit -m "feat: map pool/token unavailability to a clean 503, no secret logged (#84)"
```

---

### Task 5: Runbook — Entra role, connection and tested rollback (written, not applied)

**Files:**
- Modify: `infra/azure/db-runtime-role.md` (add a managed-identity section) and/or `infra/azure/container-apps-app.md` §9 (rotation/credentials)
- Test: `backend/tests/test_docs_hygiene.py` must stay green with the new prose (no real resource names, no placeholder DSNs).

**Interfaces:** none (documentation). This task applies nothing in Azure.

- [ ] **Step 1: Write the role/grants mapping (SQL, reviewed not applied)**

In `infra/azure/db-runtime-role.md`, add a section "Managed-identity mode (#84) — procedure, not yet applied" containing the exact SQL to map the **existing** user-assigned managed identity to a PostgreSQL Entra role, with runtime-only grants mirroring `sort_app` (SELECT/INSERT/UPDATE/DELETE on the app tables, USAGE on sequences, **no** superuser, **no** CREATE, **no** DDL, **no** migration authority). Mark that the mapping and grants must be verified against the live server as a checklist item, and that existing registry/vault access is not database access. Do not include any real server, vault, resource-group or identity name — use the placeholders the other docs use, which `test_docs_hygiene` tolerates.

- [ ] **Step 2: Write the connection and the environment**

Document that managed-identity mode sets `SORT_TESTER_DB_AUTH=managed_identity` and `SORT_TESTER_DB_IDENTITY_CLIENT_ID=<identity client id>`, that the DSN carries **no password**, the user is the Entra role, `sslmode=verify-full` where the image's CA bundle is confirmed (Task 7 dependency) else `require`, and that the token is fetched per physical connection by the app.

- [ ] **Step 3: Write the tested rollback**

Document the rollback to password mode: set `SORT_TESTER_DB_AUTH=password` (or unset), confirm the Key Vault password reference still resolves, and apply on a **new revision** — a restart does not re-read the secret (cross-reference §9b). State that the rollback must be exercised before the forward cutover is trusted.

- [ ] **Step 4: Write the ordered, approval-gated deploy/verification**

List, as steps gated on separate owner approval and run by nobody as part of this work: deploy with the flag; verify hosted identity login, reconnect and token refresh; verify admin/migration still work through their intended Entra path; and only then (separately, with approval) remove the runtime password reference and consider server-wide `passwordAuth`. No step is executed here.

- [ ] **Step 5: Run docs hygiene**

Run: `backend/.venv/bin/python -m unittest backend.tests.test_docs_hygiene -v`
Expected: PASS (new prose carries no real names and no placeholder DSNs).

- [ ] **Step 6: Commit**

```bash
git add infra/azure/db-runtime-role.md infra/azure/container-apps-app.md
git commit -m "docs: managed-identity role, connection and rollback runbook, not applied (#84)"
```

---

## Self-Review

**1. Spec coverage**

- Mode selection (spec §1) → Task 1. ✅
- Token provider + no-logging + test seam (spec §2) → Task 2. ✅
- Per-physical-connection token in the pool, contract preserved (spec §3) → Task 3. ✅
- Clean 503, single tested place, healthy connections unaffected (spec §4) → Task 4. ✅
- Local dev stays password (spec §5) → Task 1 default + Task 3 password branch unchanged; the full suite runs in password mode in Tasks 3/4. ✅
- Tests: reuse, refresh, failure, no-token-in-logs, mode validation, password untouched (spec §6) → Task 2 (reuse/refresh/failure/no-log directly against the cache), Task 1 (mode validation), Task 3 (password branch untouched). ✅
- Runbook: role/grants, connection, rollback, ordered deploy (spec §7) → Task 5. ✅
- No new dependency; IMDS via stdlib keeps the container invariants (spec Dependencies) → Task 2 (no requirements edit). ✅

**2. Placeholder scan:** `<latest-stable>` in Task 2 and `<identity client id>` / placeholder names in Task 5 are deliberate fill-ins the implementer resolves against the live package/doc conventions, not skipped work; every code step carries real code. No "TBD"/"add error handling"/"write tests for the above".

**3. Type consistency:** `db_auth_mode()`, `PASSWORD_MODE`, `MANAGED_IDENTITY_MODE`, `DB_IDENTITY_CLIENT_ID_ENV_VAR` (Task 1) are the names used in Tasks 2–3. `db_access_token()` and `TokenUnavailable` (Task 2) are the names used in Tasks 3–4. `init_pool(conninfo, *, auth_mode, token_provider)` (Task 3) matches the router calls. Consistent.

## Notes and open implementation detail

- **Reuse/refresh evidence (spec §6.1–6.2):** the module's own expiry-aware cache is tested directly in Task 2 (`test_reuses_within_lifetime`, `test_refreshes_within_the_skew_window`) using a fake fetcher that returns controlled `expires_on` values — no network, no SDK. Task 3's callable test proves the pool asks the provider per physical connect.
- **Pool acquisition timeout:** the default pool `timeout` is 30s and `reconnect_timeout` 300s (bounded background retry, not a tight spin). If a faster 503 is wanted in managed-identity mode, a shorter pool `timeout` can be added in Task 3 — left out here to avoid changing password-mode behaviour; raise it with the owner if the 503 latency matters before the pilot.
